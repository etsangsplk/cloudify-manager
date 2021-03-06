#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

from collections import OrderedDict

from sqlalchemy.ext.declarative import declared_attr
from flask_security import SQLAlchemyUserDatastore, UserMixin, RoleMixin

from manager_rest.constants import (ADMIN_ROLE,
                                    USER_ROLE,
                                    SUSPENDED_ROLE,
                                    BOOTSTRAP_ADMIN_ID,
                                    DEFAULT_TENANT_ID)

from .relationships import many_to_many_relationship
from .models_base import db, SQLModelBase, UTCDateTime, CIColumn


class ProviderContext(SQLModelBase):
    __tablename__ = 'provider_context'

    id = db.Column(db.Text, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    context = db.Column(db.PickleType, nullable=False)


class Tenant(SQLModelBase):
    __tablename__ = 'tenants'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text, unique=True, index=True)

    def _get_identifier_dict(self):
        return OrderedDict({'name': self.name})

    def to_response(self):
        tenant_dict = super(Tenant, self).to_response()
        group_names = [group.name for group in self.groups]
        user_names = [user.username for user in self.all_users]
        tenant_dict['groups'] = sorted(group_names)
        tenant_dict['users'] = sorted(user_names)
        return tenant_dict

    @property
    def all_users(self):
        users_list = self.users
        for group in self.groups:
            for user in group.users:
                users_list.append(user)

        return list(set(users_list))

    @property
    def is_default_tenant(self):
        return self.id == DEFAULT_TENANT_ID


class Group(SQLModelBase):
    __tablename__ = 'groups'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = CIColumn(db.Text, unique=True, nullable=False, index=True)
    ldap_dn = CIColumn(db.Text, unique=True, nullable=True, index=True)

    def _get_identifier_dict(self):
        id_dict = OrderedDict({'name': self.name})
        if self.ldap_dn:
            id_dict['ldap_dn'] = self.ldap_dn
        return id_dict

    @declared_attr
    def tenants(cls):
        return many_to_many_relationship(cls, Tenant)

    def to_response(self):
        group_dict = super(Group, self).to_response()
        tenant_names = [tenant.name for tenant in self.tenants]
        user_names = [user.username for user in self.users]
        group_dict['tenants'] = sorted(tenant_names)
        group_dict['users'] = sorted(user_names)
        return group_dict


class Role(SQLModelBase, RoleMixin):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text, unique=True, nullable=False, index=True)

    description = db.Column(db.Text)

    def _get_identifier_dict(self):
        return OrderedDict({'name': self.name})


class User(SQLModelBase, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = CIColumn(db.String(255), index=True, unique=True)

    active = db.Column(db.Boolean)
    created_at = db.Column(UTCDateTime)
    email = db.Column(db.String(255), index=True)
    first_name = db.Column(db.String(255))
    last_login_at = db.Column(UTCDateTime, index=True)
    last_name = db.Column(db.String(255))
    password = db.Column(db.String(255))

    def _get_identifier_dict(self):
        return OrderedDict({'username': self.username})

    @declared_attr
    def roles(cls):
        return many_to_many_relationship(cls, Role)

    @declared_attr
    def groups(cls):
        return many_to_many_relationship(cls, Group)

    @declared_attr
    def tenants(cls):
        return many_to_many_relationship(cls, Tenant)

    @property
    def all_tenants(self):
        """Return all tenants associated with a user - either directly, or
        via a group the user is in

        Note: recursive membership in groups is currently not supported
        """
        tenant_list = self.tenants
        for group in self.groups:
            for tenant in group.tenants:
                tenant_list.append(tenant)

        return list(set(tenant_list))

    def to_response(self):
        user_dict = super(User, self).to_response()
        tenant_names = [tenant.name for tenant in self.all_tenants]
        group_names = [group.name for group in self.groups]
        user_dict['tenants'] = sorted(tenant_names)
        user_dict['groups'] = sorted(group_names)
        user_dict['role'] = self.role
        return user_dict

    @property
    def role(self):
        return self.roles[0].name

    @property
    def is_default_user(self):
        return self.role == USER_ROLE

    @property
    def is_admin(self):
        return self.role == ADMIN_ROLE

    @property
    def is_suspended(self):
        return self.role == SUSPENDED_ROLE

    @property
    def is_bootstrap_admin(self):
        return self.id == BOOTSTRAP_ADMIN_ID


user_datastore = SQLAlchemyUserDatastore(db, User, Role)
