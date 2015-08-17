#!/usr/bin/python

import sys, getopt
from dragonflow.db.drivers import ramcloud_nb_impl

def main(argv):
   db_ip = ''
   db_port = ''
   try:
      opts, args = getopt.getopt(['-ival', '-pval'], 'i:p:')
   except getopt.GetoptError:
      print 'table_setup.py -i <db_ip> -p <db_port>'
      sys.exit(2)
   for opt, arg in opts:
      if opt == '-h':
         print 'table_setup.py -i <db_ip> -p <db_port>'
         sys.exit()
      elif opt in ("-i"):
         db_ip = arg
      elif opt in ("-p"):
         db_port = arg
   print 'db_ip  is "', db_ip
   print 'db_port is "', db_port

   client = ramcloud_nb_impl.RamcloudNbApi(db_ip,db_port)
   client.create_tables(['chassis', 'lport', 'lswitch', 'lrouter'])

if __name__ == "__main__":
   main(sys.argv[1:])
