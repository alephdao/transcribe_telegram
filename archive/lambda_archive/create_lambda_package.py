import os
import shutil
import subprocess
import sys

def create_lambda_package():
    """
    Create a deployment package for AWS Lambda with required dependencies
    """
    # Create a clean directory for the package
    if os.path.exists('lambda_package'):
        shutil.rmtree('lambda_package')
    os.makedirs('lambda_package')
    
    # Copy the lambda function
    shutil.copy('lambda_function.py', 'lambda_package/')
    
    # Create requirements.txt with compatible versions
    requirements = [
        'python-telegram-bot==20.8',
        'google-generativeai==0.3.2',
        'python-dotenv',
        'aiohttp',
        'grpcio==1.57.0',  # Using a more stable version
        'protobuf==4.24.0'  # Matching protobuf version
    ]
    
    with open('lambda_package/requirements.txt', 'w') as f:
        f.write('\n'.join(requirements))
    
    # Install dependencies
    subprocess.check_call([
        sys.executable,
        '-m', 'pip',
        'install',
        '--platform', 'manylinux2014_x86_64',
        '--implementation', 'cp',
        '--python-version', '3.11',
        '--only-binary=:all:',
        '--target', 'lambda_package',
        '-r', 'lambda_package/requirements.txt'
    ])
    
    # Create the zip file
    shutil.make_archive('lambda_deployment', 'zip', 'lambda_package')
    
    print("Created lambda_deployment.zip")

if __name__ == "__main__":
    create_lambda_package()
