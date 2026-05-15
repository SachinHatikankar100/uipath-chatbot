We need these below 6 files

setup-app-infrastructure.sh
Dockerfile
Dcokerfile.jenkins
Jenkins
build-and-push-docker-image.sh
azure-deploy-jenkins.sh


We need azure cli so download and Verify the az cli installation with command

az --version

then type

az login

Two login 
1. az login
2. Login in portal.azure.com

In portal add a subscription. Eg. Subscription 2

Check the existing subscription
az account list --output table - It should be empty in the start if no sucbscriptions are available in the portal.azure.com

Set the account 
az account set --subscription 14019fc9-0ee5-4194-a599-dd66b745c7fc

To get details of your account type
az account show


Modified the Dockerfile - refer the comments to check the part which got updated and removed

Check and modify the Dockerfile.jenkins - no change required, by default jenkins runs on 8080 port

Check and modify the Jenkins file - need to modify as per uipath chatbot code

Check and modify the azure-deploy-jenkins.sh file - need to modify as per uipath chatbot code

Check and modify build-and-push-coker-image.sh - need to modify as per uipath chatbot code

Check and modfy the setup-app-infrastructure.sh


The firstmost script we run is azure-deploy-jenkins.sh. We may face some issue which is discussed and fixed below

Once the command runs you will get the url like 
http://jenkins-uipathchatbot-626286.eastus.azurecontainer.io:8080

and then the url will ask for a password which you will get by
running the command 

az container exec \
  --resource-group uipath-chatbot-jenkins-rg \
  --name jenkins-research-uipathchatbot \
  --exec-command 'cat /var/jenkins_home/secrets/initialAdminPassword'

My password is 5e2e26e56cd34a9199e52220ac1cb67e


Make sure the Docker engine is up and running

In the url, click on Install suggested plugins,Then setup the plugins,It will atleast 5 - 10 mins, let it complete installation and later make sure to click on skip and continue as admin

So the username will be admin and the password will the password which got from the previous step


To check where is the custom-jenkins running you can go to the azure portal 

![alt text](image-1.png)
After reaching to this location open service/repository

Thi is the image which runs over the container

Now in the Jenkins URL do below steps
1. Click on settings icon
2. Under security section, click Security
3. Scroll to CSRF Protection, check the Enable proxy compatibility

This is needed for frictionless connectivity between the Azure services and the Jenkins which is selfhosted CICD tool, Jenkins helps us to build pipeline just like github actions

![alt text](image-2.png)


Before running the  ./setup-app-infrastructure.sh. run below commands
az storage account check-name --name uipathchatbotapp626286
az acr check-name --name uipathchatbotacr626286
both should be true as ACR and Stroage account name has to be gloablly unique

Run next command to set up the infra which is 
bash ./setup-app-infrastructure.sh - this helps us to build the infra

Once the commands completes it will give few credential values

Now go to the Jenkins URL and under the Credentials, add global credentials, Click on Add credentials, click on the Secret text, Click on next and then see the below page. Click on create after adding the credentials

![alt text](image-3.png)

This action needs to be done for all the 4 IDs that appeared from the command output

which will look like this 
![alt text](image-4.png)

We need to write this command and then add it in the Jenkins secret text

$ az ad sp create-for-rbac \
  --name "jenkins-uipath-chatbot-sp" \
  --role Contributor \
  --scopes /subscriptions/$(az account show --query id -o tsv)

  This command will create service principle in azure with role based access

essentially a robot account that Jenkins will use to talk to Azure. It's how Jenkins authenticates without you typing your password every time. The output of this command is four pieces:
json{
  "appId": "...",        ← This becomes the AZURE_CLIENT_ID Jenkins credential
  "password": "...",     ← This becomes AZURE_CLIENT_SECRET
  "tenant": "...",       ← This becomes AZURE_TENANT_ID
  "displayName": "..."
}

we need to configure the below values
azure-client-id: appId
azure-tenant-id: tenant
azure-client-secret: password
azure-subscription-id: az account show --query id -o tsv

$ az ad sp create-for-rbac \
  --name "jenkins-uipath-chatbot-sp" \
  --role Contributor \
  --scopes //subscriptions/$(az account show --query id -o tsv)
Found an existing application instance: (id) dacdcd86-ce44-4564-8654-0508bff5ddde. We will patch it.
Creating 'Contributor' role assignment under scope '//subscriptions/14019fc9-0ee5-4194-a599-dd66b745c7fc'
The output includes credentials that you must protect. Be sure that you do not include these credentials in your code or check the credentials into your source control. For more information, see https://aka.ms/azadsp-cli
{
  "appId": "71bc4837-e1fb-4e1e-9492-99b9ba405920",
  "displayName": "jenkins-uipath-chatbot-sp",
  "password": "r3~8Q~g2Ziv5y9xYXbTGeSr-T7ql6.2tUP_lEdaq",
  "tenant": "cb13509b-f60a-47ff-89cd-06e941d12866"
}

Sachi@DESKTOP-OT8PHM3 MINGW64 ~/OneDrive/Desktop/LLMOpsCourse/Projects/uipath-chatbot (main)
$ az account show --query id -o tsv
14019fc9-0ee5-4194-a599-dd66b745c7fc


Other few secrets required by Jenkins were also added and now it looks like this

![alt text](image-5.png)


Next step is to configure the jenkins pipeline
Go to the Jenkins URL and do below step - basically click on new item and give one name and select pipeline and click Ok

![alt text](image-6.png)

After this step, click Github project and do below steps
![alt text](image-7.png)

![alt text](image-9.png)


Then add the webhook in the github
Whenever we push code to github automatically it will trigger the Jenkins

![alt text](image-10.png)

Use build-and-push-docker-image.sh file to build the docker image from our application and push it the ACR
bash ./build-and-push-docker-image.sh

































1. Issue

When I did 

az login --tenant f9655ee5-07be-47c3-a75f-6cd58112701b

Error I got as below:

The command failed with an unexpected error. Here is the traceback:
Unable to get authority configuration for https://login.microsoftonline.com/f9655ee5-07be-47c3-a75f-6cd58112701b. Authority would typically be in a format of https://login.microsoftonline.com/your_tenant or https://tenant_name.ciamlogin.com or https://tenant_name.b2clogin.com/tenant.onmicrosoft.com/policy.  Also please double check your tenant name or GUID is correct.

Fix is: 
Tenant id comes from Parent management group


2. Issue 

Incorrect command 
az account set --14019fc9-0ee5-4194-a599-dd66b745c7fc

Correct command is 

az account set --subscription 14019fc9-0ee5-4194-a599-dd66b745c7fc

3. In my project pyproject.toml file was missing
Why: Because in Dockerfile pyproject.toml file is needed 
Fix - create a new file and added the content required in it
It requires exact versions of all the libraries so created get_lib_versions.py file added. When this run it will autoupdate the library with correct version


4. Issue is below for the command bash ./azure-deploy-jenkins.sh 

(SubscriptionNotFound) Subscription 14019fc9-0ee5-4194-a599-dd66b745c7fc was not found.
Code: SubscriptionNotFound
Message: Subscription 14019fc9-0ee5-4194-a599-dd66b745c7fc was not found.

FIx is as follow run below command
az account list --output table should output enable
az provider show --namespace Microsoft.Storage --query "registrationState" -o tsv - should output Registered
If it says NotRegistered type command az provider register --namespace Microsoft.Storage It takes 1–5 minutes. Re-run when it shows Registered

Check if the storage account name is available
az storage account check-name --name uipathchatbotjenkinsstore626286
You want "nameAvailable": true. If it says false, change the name in the script to something else.

Now since I faced the issue (SubscriptionNotFound) I am going to run below commands
az group delete --name uipath-chatbot-jenkins-rg --yes --no-wait
1. Clean up the resource group from the failed run. The script partially succeeded — it created the resource group before failing on the storage step. If you re-run, the script will try to create it again and either skip or error noisily. Easier to just delete it first:
--no-wait returns control immediately; deletion happens in the background and takes a couple of minutes.
2. Verify your new storage account name is available:
bash ./az storage account check-name --name uipathbotjenstore626286
Then re-run:
bashbash ./azure-deploy-jenkins.sh


The real reason: it's mostly about sanity, with a small money component
There are three actual reasons to clean up a failed resource group, in order of how much they matter:
1. Sanity (the biggest reason)
When a script fails partway through, your Azure account is left in an inconsistent state:

Resource group exists ✓
Storage account does not ✗
ACR does not ✗
Jenkins container does not ✗

If you re-run the script:

az group create is idempotent — it sees the group already exists and silently succeeds. Fine.
az storage account create tries to create the storage account. If you've changed the name, it works. If you haven't, it errors.
Subsequent commands may or may not work depending on what state the previous attempt left behind.

Starting fresh from an empty subscription means every error you see is from this run, not from leftover state from a previous attempt. It makes debugging straightforward. This is the main reason.
2. Money (small but real)
Some resources start billing the moment they're created — even if they're idle and even if the script never finished. The big offenders for this particular setup:

Azure Container Instances (Jenkins container) — bills per second while running. ~$0.05/hour for the 2 CPU / 4 GB config in this script. If Jenkins gets deployed but you forget about it, that's roughly $35/month.
Azure Container Registry (Basic SKU) — flat ~$5/month while it exists, whether you use it or not.
Storage Account — pennies per month for an empty one, but it's still non-zero.
Resource Group itself — free. It's just a folder.

Your failed run didn't create any of the billable resources yet — it died at the storage step. So the failed run isn't currently costing you anything. But if you let failed attempts pile up over a week of debugging, eventually one fails after creating the Container Instance, and that one will quietly bill you.
3. Name reuse
If a resource group is in a "Deleting" state (because you deleted it but it hasn't finished), Azure won't let you create another resource group with the same name until deletion completes. This is why I suggested --no-wait — it kicks off the deletion in the background while you do other things, but you should give it a couple of minutes before re-running the script.
The honest one-liner for your blog
"Cleanup is 80% for sanity and 20% for cost control. If you don't clean up failed runs, your debugging gets harder because you can't tell which errors are from the current run vs leftover state. The cost piece is small but real — Azure Container Instances and ACR start billing the moment they're created."


5. Issue faced after command azure-deploy-jenkins.sh

(MissingSubscriptionRegistration) The subscription is not registered to use namespace 'Microsoft.ContainerRegistry'. See https://aka.ms/rps-not-found for how to register subscriptions.
Code: MissingSubscriptionRegistration
Message: The subscription is not registered to use namespace 'Microsoft.ContainerRegistry'. See https://aka.ms/rps-not-found for how to register subscriptions.
Exception Details:      (MissingSubscriptionRegistration) The subscription is not registered to use namespace 'Microsoft.ContainerRegistry'. See https://aka.ms/rps-not-found for how to register subscriptions.
        Code: MissingSubscriptionRegistration
        Message: The subscription is not registered to use namespace 'Microsoft.ContainerRegistry'. See https://aka.ms/rps-not-found for how to register subscriptions.
        Target: Microsoft.ContainerRegistry


Why :
Earlier I mentioned that every Azure subscription has to "opt in" to each resource type before it can create resources of that type. We checked Microsoft.Storage earlier — that one was already registered (which is why the storage account just succeeded).
But Microsoft.ContainerRegistry is a separate resource provider, and it hasn't been registered yet on this subscription. So when the script tries to create an ACR, Azure says "I don't know what an ACR is for this subscription — register the provider first."
This is normal for newer subscriptions. Microsoft auto-registers the common providers (Storage, Network, Compute) but lazy-registers the less common ones on first use.

Fix :
az provider register --namespace Microsoft.ContainerRegistry
This kicks off the registration. It takes anywhere from 30 seconds to 5 minutes. Check status with:
bashaz provider show --namespace Microsoft.ContainerRegistry --query "registrationState" -o tsv
Run that every 30 seconds or so. You're waiting for it to change from Registering to Registered

Proactive fix by registering AzureContainerInstance

az provider register --namespace Microsoft.ContainerInstance

To see which providers are already registered vs not:
az provider list --query "[?registrationState=='Registered'].namespace" -o tsv

Note:
Deleting the RG is sometimes necessary (when a resource is in a stuck/broken state), but for clean provider-registration failures like this one, just re-running works.

Now how to know which providers needs to be registered
doing it by reading each az <command> and translating it to a provider namespace, which is a fairly mechanical pattern:

az storage * → Microsoft.Storage
az acr * → Microsoft.ContainerRegistry
az container * (ACI) → Microsoft.ContainerInstance
az containerapp * → Microsoft.App (this one is sneaky — the CLI command says "containerapp" but the provider is Microsoft.App)
az vm * → Microsoft.Compute
az network * → Microsoft.Network
az keyvault * → Microsoft.KeyVault
az functionapp * / az webapp * → Microsoft.Web

The mechanical version of this skill is: open the script, read every az <noun> command, look at what nouns it touches, and roughly translate to namespaces. You'll get most of them right and the others Azure will correct you on at runtime.
The two ways anyone actually learns which providers exist
Way 1 — Read the error and react. Run the script, hit the failure, register, repeat. This is what 90% of practitioners actually do. Costs you 5 minutes per missing provider on the first run. Costs you nothing on every subsequent project once you've registered them.
Way 2 — Read the documentation page that maps commands to providers. Microsoft publishes one. Search "Azure resource providers and types" — there's a master list. But honestly, looking at the list once is enough to recognize patterns; nobody references it daily.
There's a related diagnostic command worth knowing:
az provider list --query "[?registrationState!='Registered'].namespace" -o tsv
That shows unregistered providers — the inverse of what you ran. Sometimes useful when you want to see what's not available.

6. Issue when gave the command 
az ad sp create-for-rbac \
  --name "jenkins-uipath-chatbot-sp" \
  --role Contributor \
  --scopes /subscriptions/$(az account show --query id -o tsv)

  Got Error:
  Creating 'Contributor' role assignment under scope 'C:/Program Files/Git/subscriptions/14019fc9-0ee5-4194-a599-dd66b745c7fc'
  Role assignment creation failed.

  role assignment response headers: {'Cache-Control': 'no-cache', 'Pragma': 'no-cache', 'Content-Length': '135', 'Content-Type': 'application/json; charset=utf-8', 'Expires': '-1', 'x-ms-failure-cause': 'gateway', 'x-ms-request-id': 'cb446b37-0653-4a0d-adb9-2e4b850cd909', 'x-ms-correlation-request-id': 'cb446b37-0653-4a0d-adb9-2e4b850cd909', 'x-ms-routing-request-id': 'WESTINDIA:20260512T112228Z:cb446b37-0653-4a0d-adb9-2e4b850cd909', 'Strict-Transport-Security': 'max-age=31536000; includeSubDomains', 'X-Content-Type-Options': 'nosniff', 'X-Cache': 'CONFIG_NOCACHE', 'X-MSEdge-Ref': 'Ref A: AFD52B7982AA47308ED35C173863BEE2 Ref B: PNQ231110907034 Ref C: 2026-05-12T11:22:28Z', 'Date': 'Tue, 12 May 2026 11:22:27 GMT'}

(MissingSubscription) The request did not have a subscription or a valid tenant level resource provider.
Code: MissingSubscription
Message: The request did not have a subscription or a valid tenant level resource provider.


Fix is adding a double slash for the subscription

az ad sp create-for-rbac \
  --name "jenkins-uipath-chatbot-sp" \
  --role Contributor \
  --scopes //subscriptions/$(az account show --query id -o tsv)

7. Issue

$ bash ./build-and-push-docker-image.sh 
Building Docker image for UiPath Chatbot...
Tag: latest

Logging in to Azure Container Registry...
You may want to use 'az acr login -n uipathchatbotacr626286 --expose-token' to get a refresh token, which does not require Docker to be installed.
2026-05-12 14:31:06.056032 An error occurred: DOCKER_COMMAND_ERROR
error during connect: Get "http://%2F%2F.%2Fpipe%2FdockerDesktopLinuxEngine/v1.51/containers/json": open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.

Fix it by running the docker application

8.