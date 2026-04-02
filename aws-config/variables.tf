variable "aws_region" {
  type        = string
  description = "The AWS region to deploy into"
  default     = "us-east-1"
}

variable "vpc_cidr_block" {
  type        = string
  description = "CIDR block for the VPC"
  default     = "10.0.0.0/24"
}

variable "subnet_cidr_block" {
  type        = string
  description = "CIDR block for the Subnet"
  default     = "10.0.0.0/24"
}

variable "ec2_ami_id" {
  type        = string
  description = "The exact AMI ID for the EC2 instances"
}

variable "ec2_instance_type" {
  type        = string
  description = "The EC2 instance type (e.g., t2.micro, t3.small)"
}