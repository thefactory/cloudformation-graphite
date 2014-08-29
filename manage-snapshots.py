#!/usr/bin/env python
import argparse
import boto.cloudformation
import boto.ec2


class SnapshotManager(object):
    STACK_PARAM = 'GraphiteEbsSnapshot'
    
    def __init__(self, region, stack, volume, aws_access_key_id=None, aws_secret_access_key=None):
        self.region = region
        self.stack = stack
        self.volume = volume
        if aws_access_key_id and aws_secret_access_key:
            self.ec2_conn = boto.ec2.connect_to_region(region, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
            self.cfn_conn = boto.cloudformation.connect_to_region(region, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
        else:
            self.ec2_conn = boto.ec2.connect_to_region(region)
            self.cfn_conn = boto.cloudformation.connect_to_region(region)
    
    def create_snapshot(self):
        print 'Creating snapshot for volume {volume}'.format(volume=self.volume)
        description = 'Created from {volume} for stack {stack}'.format(volume=self.volume, stack=self.stack)
        return self.ec2_conn.create_snapshot(self.volume, description)
    
    def get_completed_snapshots(self):
        return sorted([s for s in self.ec2_conn.get_all_snapshots(filters={'volume-id': self.volume}) if s.status=='completed'], key=lambda s: s.start_time)
        
    def update_stack_snapshot(self, snapshot):
        print 'Updating {param} on stack {stack} to {snap}'.format(param=self.STACK_PARAM, stack=self.stack, snap=snapshot)
        params = [(p.key, p.value) for p in self.cfn_conn.describe_stacks(self.stack)[0].parameters if p.key != self.STACK_PARAM]
        params.append((self.STACK_PARAM, snapshot))
        template = self.cfn_conn.get_template(self.stack)['GetTemplateResponse']['GetTemplateResult']['TemplateBody']
        self.cfn_conn.update_stack(self.stack, template_body=template, parameters=params, capabilities=['CAPABILITY_IAM'])
    
    def trim_snapshots(self, keep=5):
        for snapshot in self.get_completed_snapshots()[:-keep]:
            print 'Deleting snapshot {snap}'.format(snap=snapshot.id)
            self.ec2_conn.delete_snapshot(snapshot.id)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', metavar='COMMAND', help='command', choices=['create', 'update-stack', 'trim'])
    parser.add_argument('-v', dest='volume', help='EBS volume id', required=True)
    parser.add_argument('-s', dest='stack', help='CloudFormation stack ID or name', required=True)
    parser.add_argument('-r', dest='region', help='AWS Region', required=True)
    parser.add_argument('-m', dest='max', help='Max number of snapshots to keep when trimming', default=5, type=int)
    parser.add_argument('--key-id', dest='key_id', help='AWS access key id')
    parser.add_argument('--secret-key', dest='secret_key', help='AWS secret access key')
    args = parser.parse_args()
        
    sm = SnapshotManager(args.region, args.stack, args.volume, args.key_id, args.secret_key)
    if args.command == 'create':
        sm.create_snapshot()
    elif args.command == 'update-stack':
        snapshots = sm.get_completed_snapshots()
        sm.update_stack_snapshot(snapshots[-1].id)
    elif args.command == 'trim':
        sm.trim_snapshots(args.max)
        

if __name__ == '__main__':
    main()