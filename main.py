from itertools import islice
import boto3
import texttable

ec2_client = boto3.client('ec2')
lambda_client = boto3.client('lambda')
elb_client = boto3.client('elb')
elbv2_client = boto3.client('elbv2')
rds_client = boto3.client('rds')
ecs_client = boto3.client('ecs')

print('Retrieving all security groups ...')
paginator = ec2_client.get_paginator('describe_security_groups')
page_iterator = paginator.paginate()

security_groups = []
for page in page_iterator:
    security_groups.extend(page['SecurityGroups'])


print('\nExternally Referenced Security Groups:')
list_length = 200
external_sgs = set()
for sublist in [security_groups[i:i+list_length] for i in range(0, len(security_groups), list_length)]:
    response = ec2_client.describe_security_group_references(
        GroupId=[sg['GroupId'] for sg in sublist]
    )
    external_sgs.update(set(response['SecurityGroupReferenceSet']))

print(external_sgs)


print('\nStale Security Groups')
stale_sgs = set()
paginator = ec2_client.get_paginator('describe_stale_security_groups')
page_iterator = paginator.paginate(VpcId=security_groups[0]['VpcId'])
for page in page_iterator:
    stale_sgs.update(set(page['StaleSecurityGroupSet']))

print('Lambda Security Groups:')
paginator = lambda_client.get_paginator('list_functions')
page_iterator = paginator.paginate()
lambda_functions = []
for page in page_iterator:
    lambda_functions.extend(page['Functions'])


lambda_sgs = set()
for function in lambda_functions:
    if 'VpcConfig' in function:
        lambda_sgs.update(set(function['VpcConfig']['SecurityGroupIds']))

print(lambda_sgs)


print('\nELB Classic Security Groups:')
paginator = elb_client.get_paginator('describe_load_balancers')
page_iterator = paginator.paginate()
elbs = []
for page in page_iterator:
    elbs.extend(page['LoadBalancerDescriptions'])


elb_sgs = set()
for elb in elbs:
    elb_sgs.update(set(elb['SecurityGroups']))

print(elb_sgs)


print('\nELBv2 Security Groups:')
paginator = elbv2_client.get_paginator('describe_load_balancers')
page_iterator = paginator.paginate()
elbv2s = []
for page in page_iterator:
    elbv2s.extend(page['LoadBalancers'])


elbv2_sgs = set()
for elbv2 in elbv2s:
    if 'SecurityGroups' in elbv2:
        elbv2_sgs.update(set(elbv2['SecurityGroups']))

print(elbv2_sgs)


print('\nRDS Security Groups:')
paginator = rds_client.get_paginator('describe_db_security_groups')
page_iterator = paginator.paginate()
rds_db_securitygroups = []
for page in page_iterator:
    rds_db_securitygroups.extend(page['DBSecurityGroups'])

rds_sgs = set()
for rds_db_sg in rds_db_securitygroups:
    rds_sgs.update(set([sg['EC2SecurityGroupId'] for sg in rds_db_sg['EC2SecurityGroups']]))


paginator = rds_client.get_paginator('describe_db_instances')
page_iterator = paginator.paginate()
rds_db_instances = []
for page in page_iterator:
    rds_db_instances.extend(page['DBInstances'])

for rds_db_instance in rds_db_instances:
    rds_sgs.update(set([sg['VpcSecurityGroupId'] for sg in rds_db_instance['VpcSecurityGroups']]))

print(rds_sgs)


print('\nECS Security Groups:')
fargate_services = []
fargate_sgs = set()

for cluster_arn in ecs_client.list_clusters().get('clusterArns', None):
    paginator = ecs_client.get_paginator('list_services')
    page_iterator = paginator.paginate(cluster=cluster_arn, launchType='FARGATE')
    service_arns = []

    for page in page_iterator:
        service_arns.extend(page['serviceArns'])


    list_length = 10
    for sublist in [service_arns[i:i+list_length] for i in range(0, len(service_arns), list_length)]:
        response = ecs_client.describe_services(cluster=cluster_arn, services=sublist)
        for service in response['services']:
            fargate_services.append(service)
            if 'networkConfiguration' in service and 'awsvpcConfiguration' in service['networkConfiguration'] and 'securityGroups' in service['networkConfiguration']['awsvpcConfiguration']:
                fargate_sgs.update(set(service['networkConfiguration']['awsvpcConfiguration']['securityGroups']))

print(fargate_sgs)


print('\n=================\n')


print('\n All SGS:')
all_sgs = set([sg['GroupId'] for sg in security_groups])
print(all_sgs)



print('\n Used SGS:')
used_sgs = lambda_sgs.union(fargate_sgs, elb_sgs, elbv2_sgs, rds_sgs)
print(used_sgs)

print('\nStale SGS:')
print(stale_sgs)

print('\n Unused SGS:')
unused_sgs = all_sgs.difference(used_sgs)
print(unused_sgs)

table = texttable.Texttable()
table.add_row(['id', 'name'])
items = [[sg['GroupId'], sg['GroupName']] for sg in security_groups if sg['GroupId'] in unused_sgs]
table.add_rows( items)
print(table.draw())
# print(all_sgs.difference(used_sgs))

print('\n=================\n')
