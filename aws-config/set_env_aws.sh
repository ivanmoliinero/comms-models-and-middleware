#!/bin/bash

# Detect if we are running in Zsh or Bash to handle 'read' correctly
set_aws_var() {
    local var_name=$1
    local prompt_text=$2
    local user_input

    if [ -n "$ZSH_VERSION" ]; then
        read "user_input?$prompt_text"
    else
        read -p "$prompt_text" user_input
    fi
    export "$var_name"="$user_input"
}

# Clear existing variables
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN

# Execute prompts
set_aws_var "AWS_ACCESS_KEY_ID" "Enter AWS Access Key ID: "
set_aws_var "AWS_SECRET_ACCESS_KEY" "Enter AWS Secret Access Key: "
set_aws_var "AWS_SESSION_TOKEN" "Enter AWS Session Token: "

echo "---------------------------------------"
echo "AWS environment variables have been set."
