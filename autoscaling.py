import boto3
import botocore
import os
import requests
import time
import json
import re
from botocore.exceptions import ClientError

with open('auto-scaling-config.json') as file:
    configuration = json.load(file)

LOAD_GENERATOR_AMI = configuration['load_generator_ami']
AUTO_SCALING_GROUP_AMI = configuration['auto_scaling_group_ami']
INSTANCE_TYPE = configuration['instance_type']
LOAD_BALANCER_NAME =  configuration['load_balancer_name']
LAUNCH_CONFIGURATION_NAME = configuration['launch_configuration_name']
AUTO_SCALING_GROUP_NAME = configuration['auto_scaling_group_name']
ASG_MAX_SIZE = configuration['ags_max_size']
ASG_MIN_SIZE = configuration['ags_min_size']
ASG_DEFAULT_COOL_DOWN_PERIOD = configuration['asg_default_cool_down_period']
COOL_DOWN_PERIOD_SCALE_IN = configuration['cool_down_period_scale_in']
COOL_DOWN_PERIOD_SCALE_OUT = configuration['cool_down_period_scale_out']
SCALE_OUT_ADJUSTMENT = configuration['scale_out_adjustment']
SCALE_IN_ADJUSTMENT = configuration['scale_in_adjustment']
ALARM_PERIOD = configuration['alarm_period']
CPU_LOWER_THRESHOLD = configuration['cpu_lower_threshold']
CPU_UPPER_THRESHOLD = configuration['cpu_upper_threshold']
ALARM_EVALUATION_PERIODS_SCALE_IN = configuration['alarm_evaluation_periods_scale_out']
ALARM_EVALUATION_PERIODS_SCALE_OUT = configuration['alarm_evaluation_periods_scale_in'] 
KEY_NAME = configuration['key_name']
AUTO_SCALING_TARGET_GROUP = configuration['auto_scaling_target_group']
HEALTH_CHECK_GRACE_PERIOD = configuration['health_check_grace_period']


tag_pairs = [
    ("AIENG", "3"),
]
TAGS = [{'Key': k, 'Value': v} for k, v in tag_pairs]

TEST_NAME_REGEX = r'name=(.*log)'


def create_instance(ec2, res, ami, sg_id, ids):
    """
    Given AMI, create and return an AWS EC2 instance object
    :param ami: AMI image name to launch the instance with
    :param sg_id: id of the security group to be attached to instance
    :return: instance object
    """

    # TODO: Create an EC2 instance
    instance = ec2.run_instances(
        InstanceType=configuration['instance_type'],
        MaxCount=1,
        MinCount=1,
        ImageId=ami,
        SecurityGroupIds=[sg_id],
        TagSpecifications=[{
            'ResourceType': 'instance',
            'Tags': TAGS
        }]
        )     
    ids.append(instance['Instances'][0]['InstanceId'])
    curInstance = res.Instance(ids[-1])
    while curInstance.state['Name'] != 'running':
        #print(curInstance.state['Name'])
        time.sleep(1)
        curInstance.load()
    return curInstance

    return instance


def initialize_test(load_generator_dns, first_web_service_dns):
    """
    Start the auto scaling test
    :param lg_dns: Load Generator DNS
    :param first_web_service_dns: Web service DNS
    :return: Log file name
    """

    add_ws_string = 'http://{}/autoscaling?dns={}'.format(
        load_generator_dns, first_web_service_dns
    )
    response = None
    while not response or response.status_code != 200:
        try:
            response = requests.get(add_ws_string)
        except requests.exceptions.ConnectionError:
            time.sleep(1)
            pass 

    # TODO: return log File name
    return get_test_id(response)


def initialize_warmup(load_generator_dns, load_balancer_dns):
    """
    Start the warmup test
    :param lg_dns: Load Generator DNS
    :param load_balancer_dns: Load Balancer DNS
    :return: Log file name
    """

    add_ws_string = 'http://{}/warmup?dns={}'.format(
        load_generator_dns, load_balancer_dns
    )
    response = None
    while not response or response.status_code != 200:
        try:
            response = requests.get(add_ws_string)
        except requests.exceptions.ConnectionError:
            time.sleep(1)
            pass  

    # TODO: return log File name
    return get_test_id(response)


def get_test_id(response):
    """
    Extracts the test id from the server response.
    :param response: the server response.
    :return: the test name (log file name).
    """
    response_text = response.text

    regexpr = re.compile(TEST_NAME_REGEX)

    return regexpr.findall(response_text)[0]
    


def print_section(msg):
    """
    Print a section separator including given message
    :param msg: message
    :return: None
    """
    print(('#' * 40) + '\n# ' + msg + '\n' + ('#' * 40))


def is_test_complete(load_generator_dns, log_name):
    """
    Check if auto scaling test is complete
    :param load_generator_dns: lg dns
    :param log_name: log file name
    :return: True if Auto Scaling test is complete and False otherwise.
    """
    log_string = 'http://{}/log?name={}'.format(load_generator_dns, log_name)

    # creates a log file for submission and monitoring
    f = open(log_name + ".log", "w")
    log_text = requests.get(log_string).text
    f.write(log_text)
    f.close()

    return '[Test finished]' in log_text


def main():

    print_section('1 - create two security groups')

    PERMISSIONS = [
        {'IpProtocol': 'tcp',
         'FromPort': 80,
         'ToPort': 80,
         'IpRanges': [{'CidrIp': '0.0.0.0/0'}],
         'Ipv6Ranges': [{'CidrIpv6': '::/0'}],
         }
    ]

    ec2_client = boto3.client('ec2', region_name='us-east-1')
    ec2_res = boto3.resource('ec2', region_name='us-east-1')


    sg1_id = None  # Security group for Load Generator instances
    vpc_response = ec2_client.describe_vpcs()
    vpc_id = vpc_response.get('Vpcs', [{}])[0].get('VpcId', '')
    subnet_response = ec2_client.describe_subnets()
    subnets = []
    for subnet_info in subnet_response['Subnets']:
        subnets.append(subnet_info['SubnetId'])

    try:
        response = ec2_client.create_security_group(GroupName='Load Generator', Description='DESCRIPTION', VpcId=vpc_id)
        sg1_id = response['GroupId']
        data = ec2_client.authorize_security_group_ingress(GroupId=sg1_id, IpPermissions=PERMISSIONS)
    except ClientError as e:
        print(e)

    sg2_id = None  
    try:
        response = ec2_client.create_security_group(GroupName='ASG,ELB', Description='DESCRIPTION', VpcId=vpc_id)
        sg2_id = response['GroupId']
        data = ec2_client.authorize_security_group_ingress(GroupId=sg2_id, IpPermissions=PERMISSIONS)
    except ClientError as e:
        print(e)

    print_section('2 - create LG')
    ids = list()

    lg = create_instance(ec2_client, ec2_res, LOAD_GENERATOR_AMI, sg1_id, ids)
    lg_id = lg.instance_id
    lg_dns = lg.public_dns_name
    print("Load Generator running: id={} dns={}".format(lg_id, lg_dns))

    print_section('3. Create LC (Launch Config)')
    auto_scaling_client = boto3.client('autoscaling', region_name='us-east-1')
    launch_configuration = auto_scaling_client.create_launch_configuration(
        LaunchConfigurationName = LAUNCH_CONFIGURATION_NAME,
        ImageId=AUTO_SCALING_GROUP_AMI,
        InstanceType=INSTANCE_TYPE,
        SecurityGroups=[sg2_id],
        InstanceMonitoring={'Enabled': True},
        KeyName=KEY_NAME)

    print_section('4. Create TG (Target Group)')
    ELB_client = boto3.client('elbv2', region_name='us-east-1')
    tg_response = ELB_client.create_target_group(
        Name = AUTO_SCALING_TARGET_GROUP,
        Protocol='HTTP',
        Port=80,
        HealthCheckPath='/', 
        HealthCheckProtocol='HTTP',
        VpcId= vpc_id)
    tg_arn = tg_response['TargetGroups'][0]['TargetGroupArn']

    print_section('5. Create ELB (Elastic/Application Load Balancer)')

    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/elbv2.html


    elb_load_balancer_response = ELB_client.create_load_balancer(
        SecurityGroups=[sg2_id],
        Subnets = subnets,
        Type='application',
        Name=LOAD_BALANCER_NAME)
    lb_arn = elb_load_balancer_response['LoadBalancers'][0]['LoadBalancerArn']
    lb_dns = elb_load_balancer_response['LoadBalancers'][0]['DNSName']
    print("lb started. ARN={}, DNS={}".format(lb_arn, lb_dns))


    print_section('6. Associate ELB with target group')
    listener_response = ELB_client.create_listener( 
        LoadBalancerArn=lb_arn,
        Protocol='HTTP',
        Port=80,
        DefaultActions=[{'Type': 'forward', 'TargetGroupArn': tg_arn}])
    listener_arn = listener_response['Listeners'][0]['ListenerArn']

    print_section('7. Create ASG (Auto Scaling Group)')
    subnets_string = ",".join(subnets)
    auto_scaling_group_response = auto_scaling_client.create_auto_scaling_group(
        AutoScalingGroupName=AUTO_SCALING_GROUP_NAME,
        VPCZoneIdentifier = subnets_string,
        DesiredCapacity=2,
        LaunchConfigurationName=LAUNCH_CONFIGURATION_NAME,
        TargetGroupARNs=[tg_arn],
        HealthCheckGracePeriod=HEALTH_CHECK_GRACE_PERIOD,
        MinSize=ASG_MIN_SIZE,
        MaxSize=ASG_MAX_SIZE,
        DefaultCooldown=ASG_DEFAULT_COOL_DOWN_PERIOD,
        HealthCheckType='EC2',
        Tags = TAGS
    )

    print_section('8. Create policy and attached to ASG')
    policy_scale_out_response = auto_scaling_client.put_scaling_policy(
        AutoScalingGroupName=AUTO_SCALING_GROUP_NAME,
        PolicyName='scale_out',
        AdjustmentType='ChangeInCapacity',
        Cooldown=COOL_DOWN_PERIOD_SCALE_OUT,
        ScalingAdjustment=SCALE_OUT_ADJUSTMENT
    )
    policy_scale_out_arn = policy_scale_out_response['PolicyARN']
    policy_scale_in_response = auto_scaling_client.put_scaling_policy(
        AutoScalingGroupName=AUTO_SCALING_GROUP_NAME,
        PolicyName='scale_in',
        AdjustmentType='ChangeInCapacity',
        Cooldown=COOL_DOWN_PERIOD_SCALE_IN,
        ScalingAdjustment=SCALE_IN_ADJUSTMENT
    )
    policy_scale_in_arn = policy_scale_in_response['PolicyARN']



    print_section('9. Create Cloud Watch alarm. Action is to invoke policy.')
    cloudwatch_client = boto3.client('cloudwatch', region_name='us-east-1')
    cloudwatch_client.put_metric_alarm(
        AlarmName='highCPUUtil',
        ActionsEnabled=True,
        Statistic='Average',
        Dimensions = [{"Name": "InstanceId","Value": lg_id}],
        Period=ALARM_PERIOD,
        Threshold=CPU_UPPER_THRESHOLD,
        ComparisonOperator='GreaterThanOrEqualToThreshold',
        AlarmActions=[policy_scale_out_arn],
        Namespace='AWS/EC2',
        MetricName='CPUUtilization',
        EvaluationPeriods=ALARM_EVALUATION_PERIODS_SCALE_OUT,
    )

    cloudwatch_client.put_metric_alarm(
        AlarmName='lowCPUUtil',
        ActionsEnabled=True,
        Statistic='Average',
        Dimensions = [{"Name": "InstanceId","Value": lg_id}],
        Period=ALARM_PERIOD,
        Threshold=CPU_LOWER_THRESHOLD,
        ComparisonOperator='LessThanOrEqualToThreshold',
        Namespace='AWS/EC2',
        AlarmActions=[policy_scale_in_arn],
        MetricName='CPUUtilization',
        EvaluationPeriods=ALARM_EVALUATION_PERIODS_SCALE_IN,
    )



    print_section('10. Submit ELB DNS to LG, starting auto scaling test.')
    # May take a few minutes to start actual test after warm up test finishes
    log_name = initialize_test(lg_dns, lb_dns)
    while not is_test_complete(lg_dns, log_name):
        time.sleep(1)

    #destroy all resouces
    try:
        #cloud watch
        cloudwatch_client.delete_alarms(
            AlarmNames=['highCPUUtil','lowCPUUtil']
        )
        print('Cloudwatch Deleted')
        #policy
        auto_scaling_client.delete_policy(
            AutoScalingGroupName=AUTO_SCALING_GROUP_NAME,
            PolicyName='scale_in'
        )
        auto_scaling_client.delete_policy(
            AutoScalingGroupName=AUTO_SCALING_GROUP_NAME,
            PolicyName='scale_out'
        )
        print('Policy Deleted')
        #auto_scaling_group
        auto_scaling_client.delete_auto_scaling_group(
            AutoScalingGroupName=AUTO_SCALING_GROUP_NAME,
            ForceDelete=True
        )
        print('Auto Scaling Group Deleted')
        #listener 
        ELB_client.delete_listener(
            ListenerArn=listener_arn
        )
        print('Listener Deleted')
        #load balancer
        ELB_client.delete_load_balancer(
            LoadBalancerArn=lb_arn
        )
        print('Load balancer Deleted')
        #Target group
        ELB_client.delete_target_group(
            TargetGroupArn=tg_arn
        )
        print('Target Group Deleted')
        #instance
        id = ids[0]
        ec2_res.Instance(id).terminate()
        while(ec2_res.Instance(id).state['Name'] != 'terminated'):
            ec2_res.Instance(id).load()
        print('Load Generator Deleted')
        #configration
        auto_scaling_client.delete_launch_configuration(
            LaunchConfigurationName=LAUNCH_CONFIGURATION_NAME
        )
        print('Launch Configuration Deleted')
        #security group
        ec2_client.delete_security_group(GroupId=sg1_id)
        ec2_client.delete_security_group(GroupId=sg2_id)
        print('Security Group Deleted')

    except ClientError as e:
        print(e)


if __name__ == "__main__":
    main()
