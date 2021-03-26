import boto3
import time
from datetime import datetime
import subprocess

user_data="""#!/bin/bash
yum update -y
yum install httpd -y
systemctl enable httpd
systemctl start httpd"""

ec2 = boto3.resource('ec2')
s3 = boto3.resource("s3")
cloudwatch = boto3.resource('cloudwatch')

print(" ")		#Welcome Prompt
print("Hello! This script requires a keypair and security group with inbound TCP port rules. You can create them with this script or use your own.")
print(" ")

while True:  #will loop until the "new_keypair" variable is created successfully, protects crashing from user inputting bad data
   key_query = input("Do you want to create a new key pair?(y/n) ")   #If user decides to create a key pair this code block is run
   if("y" in key_query.lower()):
      keypair_name = input("Please enter a name for your new keypair file: ")
      try:
         new_keypair = ec2.create_key_pair(KeyName = keypair_name)   #new key creation attempt with name as input by user
         pemfile = keypair_name+'.pem'
         with open('./'+pemfile, 'w') as file:
            file.write(new_keypair.key_material)
         access_pem = "sudo chmod 400 {}".format(pemfile)
         subprocess.run(access_pem, shell=True)
      except Exception as error:
         print(error)

      if(key_query is not None and "new_keypair" in globals()):  #breaks loop when the "new_keypair" file is created
         break

   if("n" in key_query.lower()):
         break


while True:
   secgrp_query = input("Do you want to create a new security group?(y/n) ")   #similar to keypair creation loop
   if("y" in secgrp_query.lower()):
      sec_grp_name = input("Please enter a unique name for your new security group: ")
      try:
         security_group = ec2.create_security_group(
                        Description='SecGroup',
                        GroupName=sec_grp_name,   #name will be as input by user
         )

         security_group.authorize_ingress(
             GroupName=sec_grp_name,
             IpPermissions=[
              {
               'FromPort': 22,			#this information creates a rule for the new security group. Allows incoming TCP traffic, ports 22 - 80 from all IP's
               'IpProtocol': 'tcp',
               'IpRanges': [
                        {
                        'CidrIp' : '0.0.0.0/0'
                        }
                        ],
               'ToPort': 80,
           }
               ]
         )
      except Exception as error:
         print(error)

      if(secgrp_query is not None and "security_group" in globals()):
         break

   if("n" in secgrp_query.lower()):
      break

while True:  #this while loop is to bring a robust mechanism to deal with the user inputting the wrong string for their key or security group
   if("n" in key_query.lower()):
      keypair_name = input("Please enter the name of your existing keypair file: ")
   if("n" in secgrp_query.lower()):
      sec_grp_name = input("Enter a suitable security group name from your list: ")
   print("Creating EC2 Instance..")

   try:
      new_instances = ec2.create_instances(
                            ImageId='ami-096f43ef67d75e998',
                            MinCount=1,
                            MaxCount=1,
                            InstanceType='t2.nano',
                            UserData=user_data,
                            TagSpecifications=[ { 'ResourceType': 'instance',  
                                                  'Tags':[ 
                                                           { 'Key' : 'Name', 'Value' : 'My Web Server' },
                                                          ] } ],
                                    SecurityGroups=[ sec_grp_name ],
                            KeyName=keypair_name
      )
   except Exception as error:
      print ("Error: " + str(error))
      print ("Please check your key and security group")
      print (" ")
   if ("new_instances" in globals()):  #if the new_instances list was populated and it exists, then the loop will break and the script will continue
      break

instance_id = new_instances[0].id
instance = ec2.Instance(instance_id)
instance.wait_until_running()
instance.reload()
instance_ip = instance.public_ip_address
print ("Instance ID " + instance_id + " is now running, IP address is " + instance_ip)
instance.monitor()
starttime = datetime.utcnow()

bucket_name = "bucket" + datetime.now().strftime("%y%m%d%H%M%S%f")	#this is to give the automated bucket creation a guaranteed unique name
 
try:
   bucket = s3.create_bucket(
			ACL='public-read', 
			Bucket=bucket_name, 
			CreateBucketConfiguration={'LocationConstraint': 'eu-west-1'}
			)
   print ("bucket: " + bucket_name + " has been created")
except Exception as error:
   print (error)

getImage = "curl -O -s http://devops.witdemo.net/image.jpg"  #this string will be used in a subprocess command to download the data at this URL, it is an image
object_name="image.jpg"

try:
   subprocess.run(getImage,shell=True)   #the image is downloaded and stored on the local disk, in the current directory
except Exception as error:
   print (error)

try:
   s3.Object(bucket_name, object_name).put(ACL='public-read',Body=open(object_name, 'rb'))   #image is put into the bucket storage
   print (object_name + " has been uploaded to " + bucket_name)
except Exception as error:
   print (error)

subprocess.run("rm image.jpg",shell=True) #remove the local copy of image.jpg

ssh_cmd = "ssh -i {key}.pem ec2-user@{instanceip}".format(key=keypair_name,instanceip=instance_ip)  #string variable which will be called with the .format() function in later strings

#this add_html multi-line string variable is constructing a sequence of ssh requests which I call later in a subprocess command, it is requesting instance metadata from the EC2 instance
#and constructing a simple html file to display this information, it also requests the image I sent to the bucket above
add_html = """ssh -o StrictHostKeyChecking=no -i {key}.pem ec2-user@{instanceip} 'echo "Private IP Address: " > index.html'  
        {ssh} 'curl -s http://169.254.169.254/latest/meta-data/local-ipv4 >> index.html'
        {ssh} 'echo "<br>MAC Address: " >> index.html'
        {ssh} 'curl -s http://169.254.169.254/latest/meta-data/mac >> index.html'
        {ssh} 'echo "<br>Availability Zone: " >> index.html'
        {ssh} 'curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone >> index.html'
        {ssh} 'echo "<br>Here is the image: <br>" >> index.html'
        {ssh} 'echo "<img src=https://s3-eu-west-1.amazonaws.com/{bucket}/image.jpg>" >> index.html'
	{ssh} sudo cp index.html /var/www/html""".format(key=keypair_name,instanceip=instance_ip,ssh=ssh_cmd,bucket=bucket_name)

#this scp_cmd string variable is constructing another sequence of requests, this time to copy a script from the local machine to the EC2 instance and then run it
scp_cmd = """scp -q -i {key}.pem monitor.sh ec2-user@{instance}:.
        {ssh} 'sudo chmod 700 monitor.sh'
        {ssh} './monitor.sh'""".format(key=keypair_name,instance=instance_ip,ssh=ssh_cmd)

#the wait string variable is a sequence of requests for the local machine, to create a script called webwait.sh that will loop while there are no HTTPD processes running. I send this to 
#the instance via scp later, and run it to make the script wait until the instance has its web server running before proceeding
wait = """echo "Waiting for Web Server.."   
	echo "HTTPD_PROCESSES=$(ps -A | grep -c httpd)" > webwait.sh
	echo "while [ $"HTTPD_PROCESSES" -lt 1 ]" >> webwait.sh
	echo "do" >> webwait.sh 
        echo "HTTPD_PROCESSES=`expr $"(ps -A | grep -c httpd)"`" >> webwait.sh	
	echo "sleep 2" >> webwait.sh
	echo "done" >> webwait.sh"""

#cp_wait contains the requests that will send the webwait.sh file to the instance 
cp_wait = """scp -q -i {key}.pem webwait.sh ec2-user@{instance}:.
	rm webwait.sh
        {ssh} 'sudo chmod 700 webwait.sh'
        {ssh} './webwait.sh'""".format(key=keypair_name,instance=instance_ip,ssh=ssh_cmd)

print("Waiting for SSH connection..")

while True:  #this loop will repeat until a successful SSH connection is made to the EC2 server. 
   try:
      response = subprocess.run("""ssh -o StrictHostKeyChecking=no -q -i {key}.pem ec2-user@{instanceip} 'echo "SSH connection successful"'
      """.format(key=keypair_name,instanceip=instance_ip),shell=True)
   except Exception as error:
      print(error)
   if("returncode=0" in str(response)):  #queries the response to see if it has returncode=0, which is given when there is no error during its execution
      break

subprocess.run(wait,shell=True)  #this will run the list of commands in the wait string variable, creating the webwait.sh file and saving it locally

while True:
   try:
      response = subprocess.run(cp_wait,shell=True)  #this will run the list of commands in the cp_wait variable, which will copy the webwait.sh file onto the instance and run it
   except Exception as error:
      print(error)
   if("returncode=0" in str(response)):
      break

while True:
   try:
      subprocess.run(add_html,shell=True)  #this will run the list of commands in the add_html variable, which will retrieve metadata and the image, and construct a simple web page
   except Exception as error:
      print(error)
   if("returncode=0" in str(response)):
      break

while True:
   try:
      subprocess.run(scp_cmd,shell=True)  #this will copy the index.html webpage made in the previous call and paste it to the directory /var/www/html so it can be seen in a browser
   except Exception as error:
      print(error)
   if("returncode=0" in str(response)):
      print("Data has been passed to Web Server!")
      print(" ")
      break

while True:
   cloudwatch_query = input("Would you like to see CloudWatch monitoring data?(y/n)")

   if("n" in cloudwatch_query.lower()):
      print("OK - thanks for using this script. Bye!")
      break
      quit()

   if(cloudwatch_query is not None and "y" in cloudwatch_query.lower()):
      print("Gathering Data - Please Wait....")
      time.sleep(120)
      endtime = datetime.utcnow()
      
      try:
         metric_search1 = cloudwatch.metrics.filter(Namespace='AWS/EC2',
                                            MetricName='CPUUtilization',
                                            Dimensions=[{'Name':'InstanceId', 'Value': instance_id}])
   
         cpu_metric = list(metric_search1)[0]

         cpu_response = cpu_metric.get_statistics(StartTime=starttime,
				EndTime=endtime,
				Period=60,
				Statistics=['Average'])

         print ("Average CPU utilisation:", cpu_response['Datapoints'][0]['Average'], cpu_response['Datapoints'][0]['Unit'])

         metric_search2 = cloudwatch.metrics.filter(Namespace='AWS/EC2',
                                            MetricName='NetworkIn',
                                            Dimensions=[{'Name':'InstanceId', 'Value': instance_id}])
   
         network_metric = list(metric_search2)[0]

         network_response = network_metric.get_statistics(StartTime=starttime,
                                EndTime=endtime,
                                Period=60,
                                Statistics=['Sum'])

         datalist = network_response['Datapoints']
         totalBytes = 0
         for index,i in enumerate(datalist):    #take recorded input bytes measurements, and adds them up
            totalBytes = totalBytes + network_response['Datapoints'][index]['Sum']

         print ("Bytes In: " + str(totalBytes))
      except Exception as error:
         print(error)
      break


