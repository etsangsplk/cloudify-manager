#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.
#

from datetime import datetime

from flask_restful_swagger import swagger
from sqlalchemy import (
    asc,
    bindparam,
    desc,
    func,
    literal_column,
)
from toolz import dicttoolz

from manager_rest import manager_exceptions
from manager_rest.rest.rest_decorators import (
    exceptions_handled,
    insecure_rest_method,
)
from manager_rest.rest.rest_utils import get_json_and_verify_params
from manager_rest.security import SecuredResource
from manager_rest.storage.models_base import db
from manager_rest.storage.resource_models import (
    Deployment,
    Execution,
    Event,
    Log,
)


class Events(SecuredResource):

    """Events resource.

    Throgh the events endpoint a user can retrieve both events and logs as
    stored in the SQL database.

    """

    DEFAULT_SEARCH_SIZE = 10000
    ALLOWED_FILTERS = [
        (Execution, 'execution_id'),
        (Deployment, 'deployment_id'),
    ]

    @staticmethod
    def _apply_filters(query, filters):
        """Apply filters to the query."""
        for model, field in Events.ALLOWED_FILTERS:
            if field in filters:
                query = query.filter(model.id.in_(filters[field]))
        return query

    @staticmethod
    def _apply_sort(query, sort):
        """Apply sorting criteria.

        Sorting will be rejected if the field doesn't match any of the column
        names that has been selected for the query. Note that the query
        involves two models at the same time, it is not possible to just check
        a model.

        :param query: Query in which the sorting should be applied
        :type query: :class:`sqlalchemy.orm.query.Query`
        :param sort: Sorting criteria passed as a request argument
        :type sort: dict(str, str)
        :returns: Query with sorting criteria applied
        :rtype: :class:`sqlalchemy.orm.query.Query`

        """
        column_names = set(
            column_description['name']
            for column_description in query.column_descriptions
        )
        for field, order in sort.items():
            # Drop `@` prefix for compatibility
            # with old Elasticsearch based implementation
            field = field.lstrip('@')
            if field not in column_names:
                raise manager_exceptions.BadParametersError(
                    'Unknown field to sort by: {}'.format(field))

            order_func = asc if order == 'asc' else desc
            query = query.order_by(order_func(field))
        return query

    @staticmethod
    def _apply_range_filters(query, model, range_filters):
        """Apply range filters to query.

        :param query: Query in which the filtering should be applied
        :type query: :class:`sqlalchemy.orm.query.Query`
        :param model: Model to use to apply the filtering
        :type model:
            :class:`manager_rest.storage.resource_models.Event`
            :class:`manager_rest.storage.resource_models.Log`
        :param range_filters: Range filters passed as a request argument
        :type range_filters: dict(str, dict(str))
        :returns: Query with filtering applied
        :rtype: :class:`sqlalchemy.orm.query.Query`

        """
        for field, range_filter in range_filters.items():
            # Drop `@` prefix for compatibility
            # with old Elasticsearch based implementation
            field = field.lstrip('@')
            if not hasattr(model, field):
                raise manager_exceptions.BadParametersError(
                    'Unknown field to filter by range: {}'.format(field))
            query = Events._apply_range_filter(
                query, model, field, range_filter)
        return query

    @staticmethod
    def _apply_range_filter(query, model, field, range_filter):
        """Apply a range filter to query.

        :param query: Query in which the filtering should be applied
        :type query: :class:`sqlalchemy.orm.query.Query`
        :param model: Model to use to apply the filtering
        :type model:
            :class:`manager_rest.storage.resource_models.Event`
            :class:`manager_rest.storage.resource_models.Log`
        :param field: Field in the model that should be filtered
        :type field: str
        :param range_filter: Range filter passed as a request argument
        :type range_filter: dict(str)
        :returns: Query with filtering applied
        :rtype: :class:`sqlalchemy.orm.query.Query`

        """
        if 'from' in range_filter:
            query = query.filter(getattr(model, field) >= range_filter['from'])
        if 'to' in range_filter:
            query = query.filter(getattr(model, field) <= range_filter['to'])
        return query

    @staticmethod
    def _build_select_query(filters, pagination, sort, range_filters):
        """Build query used to list events for a given execution.

        :param filters:
            Filters selection.

            Valid filtering criteria are:
                - Type (return events or both events and logs):
                    {'type': ['cloudify_event', 'cloudify_log']}
                - Execution:
                    {'execution_id': <some_id>}
                - Deployment:
                    {'deployment_id': <some_id>}

            Results must match every the filtering criteria. In particular,
            filtering by a deployment and an execution that doesn't belong to
            that deployment won't return any result.
        :type filters: dict(str, str)
        :param pagination:
            Parameters used to limit results returned in a single query.
            Expected values `size` and `offset` are mapped into SQL as `LIMIT`
            and `OFFSET`.
        :type pagination: dict(str, int)
        :param sort:
            Result sorting order.

            The only field that is supported for now is @timestamp (note the
            `@` inherited from the old Elasticsearch implementation):
                {'timestamp': 'asc'}
        :type sort: dict(str, str)
        :param range_filters:
            Filter out events that don't fall in a given range.

            The only field that is supported for now is @timestamp (note the
            `@` inherited from the old Elasticsearch implementation):
                {'timestamp': {'from': <iso8601-date>, 'to': <iso8601-date>}}
        :type range_filters: dict(str, str)
        :returns:
            A SQL query that returns the events found that match the conditions
            passed as arguments.
        :rtype: :class:`sqlalchemy.orm.query.Query`

        """
        if not isinstance(filters, dict) or 'type' not in filters:
            raise manager_exceptions.BadParametersError(
                'Filter by type is expected')

        if 'cloudify_event' not in filters['type']:
            raise manager_exceptions.BadParametersError(
                'At least `type=cloudify_event` filter is expected')

        query = (
            db.session.query(
                Event.timestamp.label('timestamp'),
                Deployment.id.label('deployment_id'),
                Event.message,
                Event.message_code,
                Event.event_type,
                Event.operation,
                Event.node_id,
                literal_column('NULL').label('logger'),
                literal_column('NULL').label('level'),
                literal_column("'cloudify_event'").label('type'),
            )
            .filter(
                Event._execution_fk == Execution._storage_id,
                Execution._deployment_fk == Deployment._storage_id,
            )
        )

        query = Events._apply_filters(query, filters)
        query = Events._apply_range_filters(query, Event, range_filters)

        if 'cloudify_log' in filters['type']:
            logs_query = (
                db.session.query(
                    Log.timestamp.label('timestamp'),
                    Deployment.id.label('deployment_id'),
                    Log.message,
                    literal_column('NULL').label('message_code'),
                    literal_column('NULL').label('event_type'),
                    Log.operation,
                    Log.node_id,
                    Log.logger,
                    Log.level,
                    literal_column("'cloudify_log'").label('type'),
                )
                .filter(
                    Log._execution_fk == Execution._storage_id,
                    Execution._deployment_fk == Deployment._storage_id,
                )
            )
            logs_query = Events._apply_filters(logs_query, filters)
            logs_query = Events._apply_range_filters(
                logs_query, Log, range_filters)

            query = query.union(logs_query)

        query = Events._apply_sort(query, sort)
        query = (
            query
            .limit(bindparam('limit'))
            .offset(bindparam('offset'))
        )

        return query

    @staticmethod
    def _build_count_query(filters, range_filters):
        """Build query used to count events for a given execution.

        :param filters:
            Filters selection.

            Valid filtering criteria are:
                - Type (return events or both events and logs):
                    {'type': ['cloudify_event', 'cloudify_log']}
                - Execution:
                    {'execution_id': <some_id>}
                - Deployment:
                    {'deployment_id': <some_id>}

            Results must match every the filtering criteria. In particular,
            filtering by a deployment and an execution that doesn't belong to
            that deployment won't return any result.
        :type filters: dict(str, str)
        :param range_filters:
            Filter out events that don't fall in a given range.

            The only field that is supported for now is @timestamp (note the
            `@` inherited from the old Elasticsearch implementation):
                {'timestamp': {'from': <iso8601-date>, 'to': <iso8601-date>}}
        :type range_filters: dict(str, str)
        :returns:
            A SQL query that returns the number of events found that match the
            conditions passed as arguments.
        :rtype: :class:`sqlalchemy.orm.query.Query`

        """
        if not isinstance(filters, dict) or 'type' not in filters:
            raise manager_exceptions.BadParametersError(
                'Filter by type is expected')

        if 'cloudify_event' not in filters['type']:
            raise manager_exceptions.BadParametersError(
                'At least `type=cloudify_event` filter is expected')

        events_query = (
            db.session.query(func.count('*').label('count'))
            .filter(
                Event._execution_fk == Execution._storage_id,
                Execution._deployment_fk == Deployment._storage_id,
            )
        )

        events_query = Events._apply_filters(events_query, filters)
        events_query = Events._apply_range_filters(
            events_query, Event, range_filters)

        if 'cloudify_log' in filters['type']:
            logs_query = (
                db.session.query(func.count('*').label('count'))
                .filter(
                    Log._execution_fk == Execution._storage_id,
                    Execution._deployment_fk == Deployment._storage_id,
                )
            )
            logs_query = Events._apply_filters(logs_query, filters)
            logs_query = Events._apply_range_filters(
                logs_query, Log, range_filters)

            query = db.session.query(
                events_query.subquery().c.count +
                logs_query.subquery().c.count
            )
        else:
            query = db.session.query(events_query.subquery().c.count)

        return query

    @staticmethod
    def _map_event_to_es(_include, sql_event):
        """Restructure event data as if it was returned by elasticsearch.

        This restructuration is needed because the API in the past used
        elasticsearch as the backend and the client implementation still
        expects data that has the same shape as elasticsearch would return.

        :param _include:
            Projection used to get records from database
        :type _include: list(str)
        :param sql_event: Event data returned when SQL query was executed
        :type sql_event: :class:`sqlalchemy.util._collections.result`
        :returns: Event as would have returned by elasticsearch
        :rtype: dict(str)

        """
        event = {
            attr: getattr(sql_event, attr)
            for attr in sql_event.keys()
        }
        event['@timestamp'] = event['timestamp']

        event['message'] = {
            'text': event['message']
        }

        context_fields = [
            'deployment_id',
            'operation',
            'node_id',
        ]
        event['context'] = {
            field: event[field]
            for field in context_fields
        }
        for field in context_fields:
            del event[field]

        if event['type'] == 'cloudify_event':
            event['message']['arguments'] = None
            del event['logger']
            del event['level']
        elif event['type'] == 'cloudify_log':
            del event['event_type']

        for key, value in event.items():
            if isinstance(value, datetime):
                event[key] = '{}Z'.format(value.isoformat()[:-3])

        # Keep only keys passed in the _include request argument
        # TBD: Do the projection at the database level
        if _include is not None:
            event = dicttoolz.keyfilter(lambda key: key in _include, event)

        return event

    def _query_events(self):
        """Query events using a SQL backend.

        :returns:
            Results using a format that resembles the one used by elasticsearch
            (more information about the format in :meth:`.._map_event_to_es`)
        :rtype: dict(str)

        """
        request_dict = get_json_and_verify_params()

        es_query = request_dict['query']['bool']

        _include = None
        # This is a trick based on the elasticsearch query pattern
        # - when only a filter is used it's in a 'must' section
        # - when multiple filters are used they're in a 'should' section
        if 'should' in es_query:
            filters = {'type': ['cloudify_event', 'cloudify_log']}
        else:
            filters = {'type': ['cloudify_event']}
        filters['execution_id'] = [
            es_query['must'][0]['match']['context.execution_id'],
        ]
        pagination = {
            'size': request_dict.get('size', self.DEFAULT_SEARCH_SIZE),
            'offset': request_dict['from'],
        }
        sort = {
            field: value['order']
            for es_sort in request_dict['sort']
            for field, value in es_sort.items()
        }
        # TBD: Support range filters in API v1 if needed
        range_filters = {}

        params = {
            'limit': pagination['size'],
            'offset': pagination['offset'],
        }

        count_query = self._build_count_query(filters, range_filters)
        total = count_query.params(**params).scalar()

        select_query = self._build_select_query(
            filters, pagination, sort, range_filters)

        events = [
            self._map_event_to_es(_include, event)
            for event in select_query.params(**params).all()
        ]

        results = {
            'hits': {
                'hits': [
                    {'_source': event}
                    for event in events
                ],
                'total': total,
            },
        }

        return results

    @swagger.operation(
        nickname='events',
        notes='Returns a list of events for the provided ElasticSearch query. '
              'The response format is as ElasticSearch response format.',
        parameters=[{'name': 'body',
                     'description': 'ElasticSearch query.',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'body'}],
        consumes=['application/json']
    )
    @exceptions_handled
    @insecure_rest_method
    def get(self, **kwargs):
        """List events using a SQL backend.

        :returns: Events found in the SQL backend
        :rtype: dict(str)

        """
        return self._query_events()

    @swagger.operation(
        nickname='events',
        notes='Returns a list of events for the provided ElasticSearch query. '
              'The response format is as ElasticSearch response format.',
        parameters=[{'name': 'body',
                     'description': 'ElasticSearch query.',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'body'}],
        consumes=['application/json']
    )
    @exceptions_handled
    @insecure_rest_method
    def post(self, **kwargs):
        """
        List events for the provided Elasticsearch query
        """
        return self._query_events()
