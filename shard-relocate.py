'''
    This script takes 'UNASSINGED' shards in your ES cluster and randomly reassigns them other nodes in the cluster

    Its fixed a RED cluster a few times for me so I figured I would share it :)

    Config is located in es_hosts.yml

'''

from elasticsearch import Elasticsearch
from elasticsearch.client import CatClient, ClusterClient, NodesClient
import random
import time
import sys

def config():
    import yaml
    with open('es_hosts.yml', 'r') as f:
        doc = yaml.load(f)
    return doc

def get_data_nodes(es):
    ''' returns a list of all data nodes in a cluster '''
    nodes = NodesClient(es)
    data_nodes = []
    for nodeid, info in nodes.info()['nodes'].iteritems():
        name = info['settings']['node']['name']
        if info['settings']['node']['data'] == 'true':
            data_nodes.append(name)
    data_nodes.sort()
    return data_nodes

def relocate():
    conf = config()

    try:
        es = Elasticsearch(conf['cluster_address'])
        escat = CatClient(es)
        escluster = ClusterClient(es)
    except Exception, e:
        print("Unable to connect to ES cluster. Reason: {}".format(e))
        sys.exit(1)

    if conf['data_nodes'] == '_all_data_nodes_':
        eshosts = get_data_nodes(es)
    else:
        eshosts = conf['data_nodes']

    def get_unassigned(d):
        if d.get('state') == 'UNASSIGNED':
            return d

    shards = escat.shards()

    headers = 'index                  shard prirep state            docs    store ip            node'.split()
    lines = shards.split('\n')

    unassigned_shards = []
    for line in lines:
        mapped = dict(zip(headers,line.split()))
        unassigned = get_unassigned(mapped)
        if unassigned:
            unassigned_shards.append(get_unassigned(mapped))

    if len(unassigned_shards) == 0:
        sys.exit("No unassigned shards found, good job!")
    else:
        shardlen = len(unassigned_shards)
        print("We have {0} unassigned shards, I will now relocate them".format(shardlen))
    for index,s in enumerate(unassigned_shards):
        bodyd = { 'commands': [ { 'allocate': { 'index': s.get('index'), 'shard': s.get('shard'), 'node': random.choice(eshosts), 'allow_primary': True }  } ] }

        print bodyd
        try:
            escluster.reroute(body=bodyd)
            print("{2} of {3} - All good with shard: {0}, index: {1}".format(s.get('shard'), s.get('index'), index, shardlen))
        except Exception, e:
            print("{2} of {3} - Was unable to re-allocate shard: shard: {0}, reason: {1}".format(s, e, index, shardlen))

        time.sleep(3)

if __name__ == "__main__":
    relocate()
