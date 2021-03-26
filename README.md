# AWS_Automate

This is a python script that will automate the creation of an EC2 AWS Instance. It can create a security group and key pair, or use an existing one, depending on the users choice.
When the instance is up and running, the script will create a bucket and put a downloaded image onto it. Then the script will build a small html file, and put this into a
folder on the instance where web server information is located. Then the html file will be viewable at the instances public IP address. The script will also allow the user to
view average CPU utilisation and the number of Bytes received in the instance via cloudwatch. 
