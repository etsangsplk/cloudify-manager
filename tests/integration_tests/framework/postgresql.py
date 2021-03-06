########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
from contextlib import closing

import pg8000
from cloudify.utils import setup_logger
from integration_tests.framework import utils
from manager_rest.flask_utils import get_postgres_conf
from manager_rest.storage import db
from sqlalchemy.engine import reflection
from sqlalchemy.schema import (MetaData,
                               Table,
                               DropTable,
                               ForeignKeyConstraint,
                               DropConstraint)

logger = setup_logger('postgresql', logging.INFO)
setup_logger('postgresql.trace', logging.INFO)


def run_query(query, db_name=None):
    conf = get_postgres_conf()
    manager_ip = utils.get_manager_ip()

    db_name = db_name or conf.db_name
    with closing(pg8000.connect(database=db_name,
                                user=conf.username,
                                password=conf.password,
                                host=manager_ip)) as con:
        con.autocommit = True
        logger.info('Trying to execute SQL query: ' + query)
        with closing(con.cursor()) as cur:
            try:
                cur.execute(query)
                fetchall = cur.fetchall()
                status_message = 'ok'
            except Exception, e:
                fetchall = None
                status_message = str(e)
            return {'status': status_message, 'all': fetchall}


def safe_drop_all():
    """Creates a single transaction that *always* drops all tables, regardless
    of relationships and foreign key constraints (as opposed to `db.drop_all`)
    """

    conn = db.engine.connect()

    # the transaction only applies if the DB supports
    # transactional DDL, i.e. Postgresql, MS SQL Server
    trans = conn.begin()

    inspector = reflection.Inspector.from_engine(db.engine)

    # gather all data first before dropping anything.
    # some DBs lock after things have been dropped in
    # a transaction.
    metadata = MetaData()

    tbs = []
    all_fks = []

    for table_name in inspector.get_table_names():
        fks = []
        for fk in inspector.get_foreign_keys(table_name):
            if not fk['name']:
                continue
            fks.append(ForeignKeyConstraint((), (), name=fk['name']))
        t = Table(table_name, metadata, *fks)
        tbs.append(t)
        all_fks.extend(fks)

    for fkc in all_fks:
        conn.execute(DropConstraint(fkc))

    for table in tbs:
        conn.execute(DropTable(table))

    trans.commit()
