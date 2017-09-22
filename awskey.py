import base64
import json
import subprocess
import boto3
import rsa
import string
import random
from subprocess import Popen, PIPE

# I want to :
#   Accept as parameters the property name and value(s) to be used as the filter
#   Query EC2 for the resource
#   Get the computername,AZ,and account
#   Choose the bastion host also in the same az of the first one
#   Obtain password for bastion host and computer(s) using pems.

# I'd ideally also like to :
#  Use this information with RoyalTSC by
#    Updating the password for the bastion entry in RoyalTSC
#    Creating a temporary connection in Royal TSC for this target
#    Starting a connection to the bastion.

#Define functions
def getEC2Instance(awsenv, ec2_filter):
    boto3.setup_default_session(profile_name=awsenv)
    ec2client = boto3.client('ec2')
    response = ec2client.describe_instances(
        Filters=[
            {
                'Name': ec2_filter.get('name') ,
                'Values': ec2_filter.get('values')
             }
        ]
    )
    instanceid=response.get('Reservations')[0].get('Instances')[0].get('InstanceId')
    publicip = response.get('Reservations')[0].get('Instances')[0].get('PublicIpAddress')
    privateip = response.get('Reservations')[0].get('Instances')[0].get('PrivateIpAddress')
    az = response.get('Reservations')[0].get('Instances')[0].get('Placement').get('AvailabilityZone')
    return {'instanceid' : instanceid,'publicip': publicip,'privateip':privateip, 'az': az}

def setClipboardData(data):
    p = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
    p.stdin.write(data)
    p.stdin.close()

def getPassword(passwd):
    x = base64.b64decode(passwd.get('PasswordData'))
    if x:
        with open(key_path, 'r') as privkeyfile:
            priv = rsa.PrivateKey.load_pkcs1(privkeyfile.read())
            key = rsa.decrypt(x, priv)
    else:
        key = 'Error could not find key'
    return key

#lets get the target instance details first
# so we'll define our variables
awsenv = 'testing'
tagname = 'tag:AppGroup'
tagvalue = ['logistics-returns-cpc-observer']
ec2_filter =  {'name': tagname, 'values':tagvalue}
instance_data = getEC2Instance(awsenv, ec2_filter)
key_path = '/Users/timpringle/Documents/pems/' + awsenv + '.pem'
ec2client = boto3.client('ec2')
passwd = ec2client.get_password_data(InstanceId=instance_data['instanceid'])
key = getPassword(passwd)
clipboarddata = 'cmdkey /add:TERMSRV/' + instance_data["privateip"] + ' /user:administrator /pass:' + key + '\r' + '\n' + 'mstsc /v:' + instance_data["privateip"] + '\r' + '\n'
setClipboardData(clipboarddata)

#lets go for the bastion host credentials now
#we're going to use the availability zone of the
#target machine for selecting the host to
#rdp into
awsenv = 'shared'
tagname = 'tag:Name'
tagvalue = ['shared-windows-bastion-host*']
ec2_filter =  {'name': tagname, 'values':tagvalue}
instance_data = getEC2Instance(awsenv, ec2_filter)
key_path = '/Users/timpringle/Documents/pems/' + awsenv + '.pem'

ec2client = boto3.client('ec2')
passwd = ec2client.get_password_data(InstanceId=instance_data['instanceid'])
key = getPassword(passwd)

connectionstring = "rdp://administrator" + ":" + key + "@" + instance_data['publicip']

applescript = '''tell application "Royal TSX"
	activate
	adhoc "connectionstring"
end tell
'''

#Let's spark up RoyalTSX using our connection string
#No we can hold the target EC2 instance hostname/password
#In the clipboard and automatically log on to the
#Bastion :-)


applescript = applescript.replace('connectionstring',connectionstring)
p = Popen(['osascript', '-'] , stdin=PIPE, stdout=PIPE, stderr=PIPE)
stdout, stderr = p.communicate(applescript)
print (p.returncode, stdout, stderr)
