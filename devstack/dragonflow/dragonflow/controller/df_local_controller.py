# Copyright (c) 2015 OpenStack Foundation.
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

import socket
import sys
import time

import eventlet
from oslo_log import log

from neutron.agent.common import config
from neutron.i18n import _LE

from ryu.base.app_manager import AppManager
from ryu.controller.ofp_handler import OFPHandler

from dragonflow.controller.l2_app import L2App
from dragonflow.controller.l3_app import L3App
from dragonflow.db import db_store
from dragonflow.db.drivers import ovsdb_vswitch_impl

from dragonflow.db.drivers import ramcloud_nb_impl

from dragonflow.db.drivers import etcd_nb_impl

config.setup_logging()
LOG = log.getLogger("dragonflow.controller.df_local_controller")

eventlet.monkey_patch()


class DfLocalController(object):

    def __init__(self, chassis_name, ip, remote_db_ip):
        self.l3_app = None
        self.l2_app = None
        self.open_flow_app = None
        self.next_network_id = 0
        self.db_store = db_store.DbStore()
        self.nb_api = None
        self.vswitch_api = None
        self.chassis_name = chassis_name
        self.ip = ip
        self.remote_db_ip = remote_db_ip

    def run(self):
        #self.nb_api = ovsdb_nb_impl.OvsdbNbApi(self.remote_db_ip)
        self.nb_api = ramcloud_nb_impl.RamcloudNbApi(db_ip=self.remote_db_ip)
        self.nb_api.initialize()
        self.vswitch_api = ovsdb_vswitch_impl.OvsdbSwitchApi(self.ip)
        self.vswitch_api.initialize()

        app_mgr = AppManager.get_instance()
        self.open_flow_app = app_mgr.instantiate(OFPHandler, None, None)
        self.open_flow_app.start()
        kwargs = dict(
            db_store=self.db_store
        )
        self.l2_app = app_mgr.instantiate(L2App, None, **kwargs)
        self.l2_app.start()
        self.l3_app = app_mgr.instantiate(L3App, None, **kwargs)
        self.l3_app.start()
        while self.l2_app.dp is None or self.l3_app.dp is None:
            time.sleep(5)
        self.db_sync_loop()

    def db_sync_loop(self):
        while True:
            time.sleep(3)
            self.run_db_poll()

    def run_db_poll(self):
        try:
            self.nb_api.sync()

            self.vswitch_api.sync()

            self.register_chassis()

            self.create_tunnels()

            self.port_mappings()

            self.read_routers()
        except Exception as e:
            LOG.error(_LE("run_db_poll - suppressing exception"))
            LOG.error(e)

    def chassis_created(self, chassis):
        # Check if tunnel already exists to this chassis

        # Create tunnel port to this chassis
        self.vswitch_api.add_tunnel_port(chassis)

    def chassis_deleted(self, chassis):
        tunnel_ports = self.vswitch_api.get_tunnel_ports()
        for port in tunnel_ports:
            if port.get_chassis_id() == chassis.get_name():
                self.vswitch_api.delete_port(port)
                return

    def logical_port_updated(self, lport):
        if self.db_store.get_port(lport.get_id()) is not None:
            # TODO(gsagie) support updating port
            return
        chassis_to_ofport, lport_to_ofport = (
            self.vswitch_api.get_local_ports_to_ofport_mapping())
        network = self.get_network_id(lport.get_network_id())
        lport.set_external_value('local_network_id', network)

        if lport.get_chassis() == self.chassis_name:
            ofport = lport_to_ofport.get(lport.get_id(), 0)
            if ofport != 0:
                lport.set_external_value('ofport', ofport)
                lport.set_external_value('is_local', True)
                self.l2_app.add_local_port(lport.get_id(),
                                           lport.get_mac(),
                                           network,
                                           ofport,
                                           lport.get_tunnel_key())
                self.db_store.set_port(lport.get_id(), lport)
        else:
            ofport = chassis_to_ofport.get(lport.get_chassis(), 0)
            if ofport != 0:
                lport.set_external_value('ofport', ofport)
                lport.set_external_value('is_local', False)
                self.l2_app.add_remote_port(lport.get_id(),
                                            lport.get_mac(),
                                            network,
                                            ofport,
                                            lport.get_tunnel_key())
                self.db_store.set_port(lport.get_id(), lport)

    def logical_port_deleted(self, lport_id):
        lport = self.db_store.get_port(lport_id)
        if lport is None:
            return
        if lport.get_external_value('is_local'):
            self.l2_app.remove_local_port(lport.get_id(),
                                          lport.get_mac(),
                                          lport.get_external_value(
                                              'local_network_id'),
                                          lport.get_external_value(
                                              'ofport'),
                                          lport.get_tunnel_key())
            self.db_store.delete_port(lport.get_id())
        else:
            self.l2_app.remove_remote_port(lport.get_id(),
                                           lport.get_mac(),
                                           lport.get_external_value(
                                               'local_network_id'),
                                           lport.get_tunnel_key())
            self.db_store.delete_port(lport.get_id())

    def router_updated(self, router):
        pass

    def router_deleted(self, router):
        pass

    def register_chassis(self):
        chassis = self.nb_api.get_chassis(self.chassis_name)
        # TODO(gsagie) Support tunnel type change here ?

        if chassis is None:
            self.nb_api.add_chassis(self.chassis_name,
                                    self.ip,
                                    'geneve')

    def create_tunnels(self):
        tunnel_ports = {}
        t_ports = self.vswitch_api.get_tunnel_ports()
        for t_port in t_ports:
            tunnel_ports[t_port.get_chassis_id()] = t_port

        for chassis in self.nb_api.get_all_chassis():
            if chassis.get_name() in tunnel_ports:
                del tunnel_ports[chassis.get_name()]
            elif chassis.get_name() == self.chassis_name:
                pass
            else:
                self.chassis_created(chassis)

        # Iterate all tunnel ports that needs to be deleted
        for port in tunnel_ports.values():
            self.vswitch_api.delete_port(port)

    def port_mappings(self):
        ports_to_remove = self.db_store.get_port_keys()
        for lport in self.nb_api.get_all_logical_ports():
            self.logical_port_updated(lport)
            if lport.get_id() in ports_to_remove:
                ports_to_remove.remove(lport.get_id())

        # TODO(gsagie) use port dictionary in all methods in l2 app
        # and here instead of always moving all arguments
        for port_to_remove in ports_to_remove:
            self.logical_port_deleted(port_to_remove)

    def get_network_id(self, logical_dp_id):
        network_id = self.db_store.get_network_id(logical_dp_id)
        if network_id is not None:
            return network_id
        else:
            self.next_network_id += 1
            # TODO(gsagie) verify self.next_network_id didnt wrap
            self.db_store.set_network_id(logical_dp_id, self.next_network_id)

    def read_routers(self):
        for lrouter in self.nb_api.get_routers():
            old_lrouter = self.db_store.get_router(lrouter.get_name())
            if old_lrouter is None:
                self._add_new_lrouter(lrouter)
                return
            self._update_router_interfaces(old_lrouter, lrouter)
            self.db_store.update_router(lrouter.get_name(), lrouter)

    def _update_router_interfaces(self, old_router, new_router):
        new_router_ports = new_router.get_ports()
        old_router_ports = old_router.get_ports()
        for new_port in new_router_ports:
            if new_port not in old_router_ports:
                self._add_new_router_port(new_router, new_port)
            else:
                old_router_ports.remove(new_port)

        for old_port in old_router_ports:
            self._delete_router_port(old_port)

    def _add_new_router_port(self, router, router_port):
        router_lport = self.db_store.get_port(router_port.get_name())
        self.db_store.set_router_port_tunnel_key(router_port.get_name(),
                                              router_lport.get_tunnel_key())
        self.l3_app.add_new_router_port(router, router_lport, router_port)

    def _delete_router_port(self, router_port):
        local_network_id = self.db_store.get_network_id(
            router_port.get_network_id())
        tunnel_key = self.db_store.get_router_port_tunnel_key(
            router_port.get_name())
        self.l3_app.delete_router_port(router_port, local_network_id,
                                       tunnel_key)
        self.db_store.del_router_port_tunnel_key(router_port.get_name())

    def _add_new_lrouter(self, lrouter):
        for new_port in lrouter.get_ports():
            self._add_new_router_port(lrouter, new_port)
        self.db_store.update_router(lrouter.get_name(), lrouter)


# Run this application like this:
# python df_local_controller.py <chassis_unique_name>
# <local ip address> <southbound_db_ip_address>
def main():
    chassis_name = socket.gethostname()
    ip = sys.argv[1]  # local ip '10.100.100.4'
    remote_db_ip = sys.argv[2]  # remote SB DB IP '10.100.100.4'
    controller = DfLocalController(chassis_name, ip, remote_db_ip)
    controller.run()

if __name__ == "__main__":
    main()
