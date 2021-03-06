########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

from flask_security.utils import encrypt_password

from manager_rest.storage.models import Tenant
from manager_rest.storage import user_datastore
from manager_rest.constants import (ADMIN_ROLE,
                                    USER_ROLE,
                                    SUSPENDED_ROLE,
                                    DEFAULT_TENANT_ID)


def get_admin_user():
    return {
            'username': 'admin',
            'password': 'admin',
            'role': ADMIN_ROLE
    }


def get_test_users():
    test_users = [
        {
            'username': 'alice',
            'password': 'alice_password',
            'role': ADMIN_ROLE
        },
        {
            'username': 'bob',
            'password': 'bob_password',
            'role': USER_ROLE
        },
        {
            'username': 'clair',
            'password': 'clair_password',
            'role': SUSPENDED_ROLE
        },
        {
            'username': 'dave',
            'password': 'dave_password',
            'role': USER_ROLE
        }
    ]
    return test_users


def add_users_to_db(user_list):
    default_tenant = Tenant.query.get(DEFAULT_TENANT_ID)
    for user in user_list:
        role = user_datastore.find_role(user['role'])
        user_obj = user_datastore.create_user(
            username=user['username'],
            password=encrypt_password(user['password']),
            roles=[role]
        )
        user_obj.tenants.append(default_tenant)
    user_datastore.commit()
