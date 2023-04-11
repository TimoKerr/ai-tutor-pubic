## This is the branch focused on deployment

## Docker setup
docker build --tag <image name> .
docker run -p 8080:8080 <image name>
-> Can be found at localhost:8080

## Gcloud integration
0. Google cloud registry, google cloud run, ... must be enabled. User must also be given the role storage admin!
1. gcloud auth login
1.2 gcloud init to switch configuration or project
1.3 gcloud config list gives current config and project and email
2. After the docker container works locally, push it to google cloud registry: (This builds + uploads the image. One can also just upload the image itself (that is build locally))
gcloud builds submit --tag gcr.io/PROJECT_ID/IMAGE_NAME:v1
gcloud builds submit --tag gcr.io/ai-tutor-chat/aitutor:v1
2.2 get list of images on gcr: gcloud container images list --repository=gcr.io/myproject -> Can also be seen in gc console UI
!! Remember the "serive Name" you give, it needs to be put into the firebase.json file!! (in this case: aitutor)
3. Once the image is in gcr we can run: gcloud run deploy --image gcr.io/ai-tutor-chat/aitutor:v1
must be in us-central1

4. connect to firebase hosting 
4.1 "npm init -y" gives a package.json file
4.2 "npm i- D firebase-tools" gives a node_modules folder
4.3 "node_modules/.bin/firebase init hosting" -> Starts process
4.4 remove the generated index.html
4.5 this results in a new firebase.json
4.6 set up the firebase.json to indicate what needs to be "rewrites" to fetch those parts from the docker container
4.7 check locally: node_modules/.bin/firebase serve
5. firebase deploy

Everytime a change needs to be made -> the docker image needs to be redeployed to gcr so from step 2. I don't think the firebase hosting needs to be do again.

## Setup

1. If you don’t have Python installed, [install it from here](https://www.python.org/downloads/).

2. Clone this repository.

3. Navigate into the project directory:

   ```bash
   $ cd openai-quickstart-python
   ```

4. Create a new virtual environment:

   ```bash
   $ python -m venv venv
   $ . venv/bin/activate
   ```

5. Install the requirements:

   ```bash
   $ pip install -r requirements.txt
   ```

6. Make a copy of the example environment variables file:

   ```bash
   $ cp .env.example .env
   ```

7. Add your [API key](https://beta.openai.com/account/api-keys) to the newly created `.env` file.

8. Run the app:

   ```bash
   $ flask run
   ```

You should now be able to access the app at [http://localhost:5000](http://localhost:5000)! For the full context behind this example app, check out the [tutorial](https://beta.openai.com/docs/quickstart).
