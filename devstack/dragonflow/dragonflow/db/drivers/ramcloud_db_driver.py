#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import ramcloud

from dragonflow.db import db_api


class RamCloudDbDriver(db_api.DbApi):

    def __init__(self):
        super(RamCloudDbDriver, self).__init__()
        self.client = None
        self.current_key = 0
        self.service_locator = None

    def create_tables(self, tables):
        for t in tables:
            self.client.drop_table(t)
            self.client.create_table(t)

    def initialize(self, db_ip, db_port, **args):
        self.client = ramcloud.RAMCloud()
        self.service_locator = 'fast+udp:host='+db_ip+',port='+str(db_port)+''
        self.client.connect()

    def support_publish_subscribe(self):
        return False

    def get_key(self, table, key):
        table_id = self.client.get_table_id(table)
        value, version = self.client.read(table_id, key)
        return value

    def set_key(self, table, key, value):
        table_id = self.client.get_table_id(table)
        self.client.write(table_id, key, value)

    def create_key(self, table, key, value):
        self.set_key(table, key, value)

    def delete_key(self, table, key):
        table_id = self.client.get_table_id(table)
        self.client.delete(table_id, key)

    def get_all_entries(self, table):
        res = []
        table_id = self.client.get_table_id(table)
        enumeration_state = self.client.enumerate_table_prepare(table_id)
        while True:
            key, value = self.client.enumerate_table_next(enumeration_state)
            if (key == ''):
                break
            res.append(value)
        self.client.enumerate_table_finalize(enumeration_state)
        return res

    def _allocate_unique_key(self):
        table_id = self.client.get_table_id('tunnel_key')
        key = 1
        version_exception = True
        while version_exception:
            try:
                value, version = self.client.read(table_id, key)
                prev_value = int(value)
                self.client.write(table_id, key, str(prev_value + 1), version)
                version_exception = False
                return prev_value + 1
            except ramcloud.VersionError:
                version_exception = True

    def allocate_unique_key(self):
        return self._allocate_unique_key()

    def wait_for_db_changes(self, callback):
        return #TODO: Ramcloud has no P/S ?

# Tests

def main():
    rc = RamCloudDbDriver()
    rc.initialize("127.0.0.1", "12246")
    rc.create_tables(['dragonflow', 'tunnel_key'])
    rc.create_key('tunnel_key', '1', '0')
    # Mock Data

    test_data = '{"external_ids": {"neutron:router_name": "router1"}, "name": "neutron-8b8a2dd9-698d-4fc3-aba3-379c8770d8af",' \
                '"ports": [{"network": "10.0.0.1/24", "lswitch": "neutron-8c46938d-4201-4223-abb1-8b4830ea6dcc", "mac": "fa:16:3e:e2:16:63",' \
                '"tunnel_key": 2, "lrouter": "neutron-8b8a2dd9-698d-4fc3-aba3-379c8770d8af", "name": "3fd0768f-2acd-4e5d-bba9-21be7e470571"},' \
                '{"network": "fd63:2be9:34d8::1/64", "lswitch": "neutron-8c46938d-4201-4223-abb1-8b4830ea6dcc", "mac": "fa:16:3e:f1:d1:f1",' \
                '"tunnel_key": 4, "lrouter": "neutron-8b8a2dd9-698d-4fc3-aba3-379c8770d8af", "name": "55f20f8d-e13b-436a-87cf-0bddf612561f"}]}'
    test_data_1 = '{"external_ids": {"neutron:router_name": "router3"}, "name": "neutron-8b8a2dd9-698d-4fc3-aba3-379c8770d8af",' \
                  '"ports": [{"network": "10.0.0.1/24", "lswitch": "neutron-8c46938d-4201-4223-abb1-8b4830ea6dcc", "mac": "fa:16:3e:e2:16:63",' \
                  '"tunnel_key": 2, "lrouter": "neutron-8b8a2dd9-698d-4fc3-aba3-379c8770d8af", "name": "3fd0768f-2acd-4e5d-bba9-21be7e470571"},' \
                  '{"network": "fd63:2be9:34d8::1/64", "lswitch": "neutron-8c46938d-4201-4223-abb1-8b4830ea6dcc", "mac": "fa:16:3e:f1:d1:f1",' \
                  '"tunnel_key": 4, "lrouter": "neutron-8b8a2dd9-698d-4fc3-aba3-379c8770d8af", "name": "55f20f8d-e13b-436a-87cf-0bddf612561f"}]}'
    test_data_2 = '{"external_ids": {"neutron:router_name": "router4"}, "name": "neutron-9k8b2cc3-698d-4fc3-aba3-379c8770d8af",' \
                  '"ports": [{"network": "10.0.0.1/24", "lswitch": "neutron-8c46938d-4201-4223-abb1-8b4830ea6dcc", "mac": "fa:16:3e:e2:16:63",' \
                  '"tunnel_key": 2, "lrouter": "neutron-8b8a2dd9-698d-4fc3-aba3-379c8770d8af", "name": "3fd0768f-2acd-4e5d-bba9-21be7e470571"},' \
                  '{"network": "fd63:2be9:34d8::1/64", "lswitch": "neutron-8c46938d-4201-4223-abb1-8b4830ea6dcc", "mac": "fa:16:3e:f1:d1:f1",' \
                  '"tunnel_key": 4, "lrouter": "neutron-8b8a2dd9-698d-4fc3-aba3-379c8770d8af", "name": "55f20f8d-e13b-436a-87cf-0bddf612561f"}]}'

    # UniTests
    test_nmb = 0
    output = rc.get_all_entries('dragonflow')
    test_nmb+=1
    print "######################## TEST NUMBER:" + str(test_nmb) + " ###################################"
    print "GetList - Empty database: "
    print(output)
    print
    print
    test_nmb+=1
    print "######################## TEST NUMBER:" + str(test_nmb) + " ###################################"
    rc.create_key('dragonflow', '3fd0768f-2acd-4e5d-bba9-21be7e470571', test_data)
    rc.create_key('dragonflow', '3fd0768f-2acd-4e5d-bba9-21be7e470572', test_data_2)
    output = rc.get_all_entries('dragonflow')
    print "GetList: "
    print(output)
    print
    print
    test_nmb+=1
    print "######################## TEST NUMBER:" + str(test_nmb) + " ###################################"
    output = rc.get_key('dragonflow', '3fd0768f-2acd-4e5d-bba9-21be7e470571')
    print "Get by Key 3fd0768f-2acd-4e5d-bba9-21be7e470571: "
    print (output)
    print
    print
    test_nmb+=1
    print "######################## TEST NUMBER:" + str(test_nmb) + " ###################################"
    print "Update Entry by Key 3fd0768f-2acd-4e5d-bba9-21be7e470571 (router1-> router3): "
    rc.set_key('dragonflow', '3fd0768f-2acd-4e5d-bba9-21be7e470571', test_data_1)
    output = rc.get_key('dragonflow', '3fd0768f-2acd-4e5d-bba9-21be7e470571')
    print "Updated Value"
    print (output)
    print
    print
    test_nmb+=1
    print "######################## TEST NUMBER:" + str(test_nmb) + " ###################################"
    print "Delete Value by Key 3fd0768f-2acd-4e5d-bba9-21be7e470571 and print list"
    rc.delete_key('dragonflow', '3fd0768f-2acd-4e5d-bba9-21be7e470571')
    output = rc.get_all_entries('dragonflow')
    print (output)
    print
    print
    test_nmb+=1
    print "######################## TEST NUMBER:" + str(test_nmb) + " ###################################"
    print "Allocate unique key"
    output = rc.allocate_unique_key()
    print "New allocated falue is: ", output
    print
    print
    test_nmb+=1
    print "######################## TEST NUMBER:" + str(test_nmb) + " ###################################"
    print "Allocate unique key"
    output = rc.allocate_unique_key()
    print "New allocated falue is: ", output
    print
    print
    test_nmb+=1
    print "######################## TEST NUMBER:" + str(test_nmb) + " ###################################"
    print "Allocate unique key"
    output = rc.allocate_unique_key()
    print "New allocated falue is: ", output
    print
    print
    print "###########STATIC TESTS DONE: " + str(test_nmb) + " of 6, STARTS S/N TESTS ####################"
if __name__ == '__main__':
    main()