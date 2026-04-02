# comms-models-and-middleware
To create the VPCs, EC2 instances and dependencies, run inside aws-config:
```
terraform init
terraform plan
terraform apply
```

ATTENTION: The keys and tokens from the session lab (available in AWS Details) must be exported into terminal variables.
```
# These are temporary credentials valid only for the current lab session.
# Copy and paste the entire block provided in the AWS Details panel.
export AWS_ACCESS_KEY_ID="ASIA..."
export AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCY..."
export AWS_SESSION_TOKEN="IQoJb3JpZ2luX2VjEJH//////////wEaCXVzLW..."
```
