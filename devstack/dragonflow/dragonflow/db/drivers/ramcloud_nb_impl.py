# Copyright (c) 2015 OpenStack Foundation.
#
# All Rights Reserved.
#
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
import netaddr
from oslo_serialization import jsonutils


from dragonflow.db import api_nb


class RamcloudNbApi(api_nb.NbApi):

    def __init__(self, db_ip='127.0.0.1', db_port=12246):
        super(RamcloudNbApi, self).__init__()
        self.client = ramcloud.RAMCloud()
        self.client.connect()
        self.ip = db_ip
        self.port = db_port
        self.service_locator = 'fast+udp:host='+db_ip+',port='+str(db_port)+'';

    def create_tables(self, tables):
        for t in tables:
            self.client.drop_table(t)
            self.client.create_table(t)

    def initialize(self):
        pass

    def sync(self):
        pass

    def get_chassis(self, name):
        try:
            table_id = self.client.get_table_id("chassis")
            chassis_value, got_version = self.client.read(table_id, name)
            return RamcloudChassis(chassis_value)
        except Exception:
            return None

    def get_all_chassis(self):
        table_id = self.client.get_table_id("chassis")
        res = []
        enumeration_state = self.client.enumerate_table_prepare(table_id)
        while True:
            key, value = self.client.enumerate_table_next(enumeration_state)
            if (key == ''):
                break
            res.append(RamcloudChassis(value))
        self.client.enumerate_table_finalize(enumeration_state)
        return res

    def add_chassis(self, name, ip, tunnel_type):
        table_id = self.client.get_table_id("chassis")
        chassis_value = name + ',' + ip + ',' + tunnel_type
        self.client.write(table_id, name, chassis_value)

    def get_all_logical_ports(self):
        table_id = self.client.get_table_id("lport")
        res = []
        enumeration_state = self.client.enumerate_table_prepare(table_id)
        while True:
            key, value = self.client.enumerate_table_next(enumeration_state)
            if (key == ''):
                break
            res.append(RamcloudLogicalPort(value))
        self.client.enumerate_table_finalize(enumeration_state)
        return res

    def create_lswitch(self, name, **columns):
        lswitch = {}
        lswitch['name'] = name
        for col, val in columns.items():
            lswitch[col] = val
        lswitch_json = jsonutils.dumps(lswitch)
        table_id = self.client.get_table_id("lswitch")
        self.client.write(table_id, name, lswitch_json)

    def update_lswitch(self, name, **columns):
        table_id = self.client.get_table_id("lswitch")
        lswitch_json, got_version = self.client.read(table_id, name)
        lswitch = jsonutils.loads(lswitch_json)
        for col, val in columns.items():
            lswitch[col] = val
        lswitch_json = jsonutils.dumps(lswitch)
        self.client.write(table_id, name, lswitch_json)

    def delete_lswitch(self, name):
        table_id = self.client.get_table_id("lswitch")
        self.client.delete(table_id, name)

    def create_lport(self, name, lswitch_name, **columns):
        lport = {}
        lport['name'] = name
        lport['lswitch'] = lswitch_name
        for col, val in columns.items():
            lport[col] = val
        lport_json = jsonutils.dumps(lport)
        table_id = self.client.get_table_id("lport")
        self.client.write(table_id, name, lport_json)

    def update_lport(self, name, **columns):
        table_id = self.client.get_table_id("lport")
        lport_json, got_version = self.client.read(table_id, name)
        lport = jsonutils.loads(lport_json)
        for col, val in columns.items():
            lport[col] = val
        lport_json = jsonutils.dumps(lport)
        self.client.write(table_id, name, lport_json)

    def delete_lport(self, name):
        table_id = self.client.get_table_id("lport")
        self.client.delete(table_id, name)

    def create_lrouter(self, name, **columns):
        lrouter = {}
        lrouter['name'] = name
        for col, val in columns.items():
            lrouter[col] = val
        lrouter_json = jsonutils.dumps(lrouter)
        table_id = self.client.get_table_id("lrouter")
        self.client.write(table_id, name, lrouter_json)

    def delete_lrouter(self, name):
        table_id = self.client.get_table_id("lrouter")
        self.client.delete(table_id, name)

    def add_lrouter_port(self, name, lrouter_name, lswitch, **columns):
        table_id = self.client.get_table_id("lrouter")
        lrouter_json, got_version = self.client.read(table_id, lrouter_name)
        lrouter = jsonutils.loads(lrouter_json)
        lrouter_port = {}
        lrouter_port['name'] = name
        lrouter_port['lrouter'] = lrouter_name
        lrouter_port['lswitch'] = lswitch
        for col, val in columns.items():
            lrouter_port[col] = val
        router_ports = lrouter.get('ports', [])
        router_ports.append(lrouter_port)
        lrouter['ports'] = router_ports
        lrouter_json = jsonutils.dumps(lrouter)
        self.client.write(table_id, lrouter_name, lrouter_json)

    def delete_lrouter_port(self, lrouter_name, lswitch): # is it delete ?
        table_id = self.client.get_table_id("lrouter")
        lrouter_json, got_version = self.client.read(table_id, lrouter_name)
        lrouter = jsonutils.loads(lrouter_json)

        new_ports = []
        for port in lrouter.get('ports', []):
            if port['lswitch'] != lswitch:
                new_ports.append(port)

        lrouter['ports'] = new_ports
        lrouter_json = jsonutils.dumps(lrouter)
        self.client.write(table_id, lrouter_name, lrouter_json)

    def get_routers(self):
        table_id = self.client.get_table_id("lrouter")
        res = []
        enumeration_state = self.client.enumerate_table_prepare(table_id)
        while True:
            key, value = self.client.enumerate_table_next(enumeration_state)
            if (key == ''):
                break
            res.append(RamcloudLogicalRouter(value))
        self.client.enumerate_table_finalize(enumeration_state)
        return res

class RamcloudChassis(api_nb.Chassis):

    def __init__(self, value):
        # Entry <chassis_name, chassis_ip, chassis_tunnel_type>
        self.values = value.split(',')

    def get_name(self):
        return self.values[0]

    def get_ip(self):
        return self.values[1]

    def get_encap_type(self):
        return self.values[2]


class RamcloudLogicalPort(api_nb.LogicalPort):

    def __init__(self, value):
        self.external_dict = {}
        self.lport = jsonutils.loads(value)

    def get_id(self):
        return self.lport.get('name')

    def get_ip(self):
        return self.lport['ips'][0]

    def get_mac(self):
        return self.lport['macs'][0]

    def get_chassis(self):
        return self.lport.get('chassis')

    def get_network_id(self):
        return self.lport.get('lswitch')

    def get_tunnel_key(self):
        return int(self.lport['tunnel_key'])

    def set_external_value(self, key, value):
        self.external_dict[key] = value

    def get_external_value(self, key):
        return self.external_dict.get(key)


class RamcloudLogicalRouter(api_nb.LogicalRouter):

    def __init__(self, value):
        self.lrouter = jsonutils.loads(value)

    def get_name(self):
        return self.lrouter.get('name')

    def get_ports(self):
        res = []
        for port in self.lrouter.get('ports'):
            res.append(RamcloudLogicalRouterPort(port))
        return res


class RamcloudLogicalRouterPort(api_nb.LogicalRouterPort):

    def __init__(self, value):
        self.router_port = value
        self.cidr = netaddr.IPNetwork(self.router_port['network'])

    def get_name(self):
        return self.router_port.get('name')

    def get_ip(self):
        return str(self.cidr.ip)

    def get_cidr_network(self):
        return str(self.cidr.network)

    def get_cidr_netmask(self):
        return str(self.cidr.netmask)

    def get_mac(self):
        return self.router_port.get('mac')

    def get_network_id(self):
        return self.router_port['lswitch']

    def get_network(self):
        return self.router_port['network']
