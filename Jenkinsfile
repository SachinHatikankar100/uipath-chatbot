pipeline {
    agent any

    options {
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '10'))
        disableConcurrentBuilds()
    }

    environment {
        // Azure credentials
        AZURE_CLIENT_ID = credentials('azure-client-id')
        AZURE_CLIENT_SECRET = credentials('azure-client-secret')
        AZURE_TENANT_ID = credentials('azure-tenant-id')
        AZURE_SUBSCRIPTION_ID = credentials('azure-subscription-id')

        // ACR credentials
        ACR_USERNAME = credentials('acr-username')
        ACR_PASSWORD = credentials('acr-password')

        // Storage credentials
        STORAGE_ACCOUNT_NAME = credentials('storage-account-name')
        STORAGE_ACCOUNT_KEY = credentials('storage-account-key')

        // API Keys

        OPENROUTER_API_KEY = credentials('OPENROUTER_API_KEY')
        TAVILY_API_KEY = credentials('TAVILY_API_KEY')

        UIPATH_ACCESS_TOKEN = credentials('UIPATH_ACCESS_TOKEN')
        UIPATH_ORG          = credentials('UIPATH_ORG')
        UIPATH_TENANT       = credentials('UIPATH_TENANT')
        UIPATH_FOLDER_ID    = credentials('UIPATH_FOLDER_ID')

        // App config
        APP_RESOURCE_GROUP = 'uipath-chatbot-app-rg'
        APP_NAME = 'uipath-chatbot-app'
        ACR_NAME = 'uipathchatbotacr626286'
        IMAGE_NAME = 'uipath-chatbot-app'
        CONTAINER_ENV = 'uipath-chatbot-env'
    }

    stages {
        stage('Checkout') {
            steps {
                echo 'Checking out code from Git...'
                // Clean workspace first
                cleanWs()
                // Clone the repository
                git branch: 'main',
                    url: 'https://github.com/SachinHatikankar100/uipath-chatbot.git'
            }
        }

        stage('Setup Python Environment') {
            steps {
                script {
                    echo 'Setting up Python environment...'
                    sh '''
                        python3 --version
                        python3 -m pip install --upgrade pip --break-system-packages
                    '''
                }
            }
        }

        stage('Syntax Check') {
            steps {
                script {
                    echo 'Running syntax check...'
                    sh '''
                        python3 -m py_compile chatbot.py
                        echo "Syntax check passed"
                    '''
                }
            }
        }

        stage('Login to Azure') {
            steps {
                script {
                    echo 'Logging in to Azure...'
                    sh '''
                        az login --service-principal \
                          -u $AZURE_CLIENT_ID \
                          -p $AZURE_CLIENT_SECRET \
                          --tenant $AZURE_TENANT_ID

                        az account set --subscription $AZURE_SUBSCRIPTION_ID
                    '''
                }
            }
        }

        stage('Verify Docker Image in ACR') {
            steps {
                script {
                    echo 'Verifying Docker image in ACR...'
                    def imageTag = sh(
                        script: """
                            az acr repository show-tags \
                              --name $ACR_NAME \
                              --repository $IMAGE_NAME \
                              --orderby time_desc \
                              --output tsv | head -n 1
                        """,
                        returnStdout: true
                    ).trim()

                    if (imageTag) {
                        echo "Found image tag: ${imageTag}"
                        env.IMAGE_TAG = imageTag
                    } else {
                        error "No image found in ACR. Run ./build-and-push-docker-image.sh first."
                    }
                }
            }
        }

        stage('Deploy to Azure Container Apps') {
            steps {
                script {
                    echo "Deploying image ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}..."
                    sh '''
                        if az containerapp show --name $APP_NAME --resource-group $APP_RESOURCE_GROUP > /dev/null 2>&1; then
                            echo "Updating existing Container App..."
                            az containerapp update \
                              --name $APP_NAME \
                              --resource-group $APP_RESOURCE_GROUP \
                              --image ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}
                        else
                            echo "Creating new Container App..."
                            az containerapp create \
                              --name $APP_NAME \
                              --resource-group $APP_RESOURCE_GROUP \
                              --environment $CONTAINER_ENV \
                              --image ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG} \
                              --registry-server ${ACR_NAME}.azurecr.io \
                              --registry-username $ACR_USERNAME \
                              --registry-password $ACR_PASSWORD \
                              --target-port 8000 \
                              --ingress external \
                              --min-replicas 1 \
                              --max-replicas 3 \
                              --cpu 1.0 \
                              --memory 2.0Gi
                        fi

                        echo "Adding secrets..."
                        az containerapp secret set \
                          --name $APP_NAME \
                          --resource-group $APP_RESOURCE_GROUP \
                          --secrets \
                            openrouter-api-key=$OPENROUTER_API_KEY \
                            tavily-api-key=$TAVILY_API_KEY \
                            uipath-access-token=$UIPATH_ACCESS_TOKEN \
                            uipath-org=$UIPATH_ORG \
                            uipath-tenant=$UIPATH_TENANT \
                            uipath-folder-id=$UIPATH_FOLDER_ID

                        az containerapp update \
                          --name $APP_NAME \
                          --resource-group $APP_RESOURCE_GROUP \
                          --set-env-vars \
                            OPENROUTER_API_KEY=secretref:openrouter-api-key \
                            TAVILY_API_KEY=secretref:tavily-api-key \
                            UIPATH_ACCESS_TOKEN=secretref:uipath-access-token \
                            UIPATH_ORG=secretref:uipath-org \
                            UIPATH_TENANT=secretref:uipath-tenant \
                            UIPATH_FOLDER_ID=secretref:uipath-folder-id
                    '''
                }
            }
        }

        stage('Verify Deployment') {
            steps {
                script {
                    echo 'Verifying deployment...'
                    sh '''
                        APP_URL=$(az containerapp show \
                          --name $APP_NAME \
                          --resource-group $APP_RESOURCE_GROUP \
                          --query properties.configuration.ingress.fqdn -o tsv)

                        echo "Application URL: https://$APP_URL"
                        echo "Waiting for readiness..."
                        sleep 30

                        if curl -f -s https://$APP_URL/_stcore/health > /dev/null; then
                            echo "Application is responding!"
                        else
                            echo "App may still be initializing..."
                        fi
                    '''
                }
            }
        }
    }

    post {
        success {
            echo 'Pipeline completed successfully!'
        }
        failure {
            echo 'Pipeline failed!'
        }
        always {
            script {
                echo 'Cleaning workspace...'
                // fix: wrap cleanup in node context
                node {
                    cleanWs()
                }
            }
        }
    }
}
