#!groovy

def tryStep(String message, Closure block, Closure tearDown = null) {
    try {
        block()
    }
    catch (Throwable t) {
        slackSend message: "${env.JOB_NAME}: ${message} failure ${env.BUILD_URL}", channel: '#ci-channel', color: 'danger'

        throw t
    }
    finally {
        if (tearDown) {
            tearDown()
        }
    }
}


node {
    stage("Checkout") {
        checkout scm
    }

    stage('Test') {
        tryStep "test", {
            sh "docker-compose -p gob_stuf_service -f src/.jenkins/test/docker-compose.yml build --no-cache && " +
               "docker-compose -p gob_stuf_service -f src/.jenkins/test/docker-compose.yml run -u root --rm test"

        }, {
            sh "docker-compose -p gob_stuf_service -f src/.jenkins/test/docker-compose.yml down"
        }
    }

    stage("Build image") {
        tryStep "build", {
            docker.withRegistry('https://repo.secure.amsterdam.nl','docker-registry') {
                def image = docker.build("datapunt/gob_stuf:${env.BUILD_NUMBER}",
                    "--no-cache " +
                    "--shm-size 1G " +
                    "--build-arg BUILD_ENV=acc" +
                    " src")
                image.push()
            }
        }
    }
}


String BRANCH = "${env.BRANCH_NAME}"


if (BRANCH == "develop") {

    node {
        stage('Push develop image') {
            tryStep "image tagging", {
                docker.withRegistry('https://repo.secure.amsterdam.nl','docker-registry') {
                    def image = docker.image("datapunt/gob_stuf:${env.BUILD_NUMBER}")
                    image.pull()
                    image.push("develop")
                }
            }
        }
    }
}


if (BRANCH == "master") {

    node {
        stage('Push acceptance image') {
            tryStep "image tagging", {
                docker.withRegistry('https://repo.secure.amsterdam.nl','docker-registry') {
                    def image = docker.image("datapunt/gob_stuf:${env.BUILD_NUMBER}")
                    image.pull()
                    image.push("acceptance")
                }
            }
        }
    }

    node {
        stage("Deploy to ACC") {
            tryStep "deployment", {
                build job: 'Subtask_Openstack_Playbook',
                    parameters: [
                        [$class: 'StringParameterValue', name: 'INVENTORY', value: 'acceptance'],
                        [$class: 'StringParameterValue', name: 'PLAYBOOK', value: 'deploy-gob-stuf.yml'],
                    ]
            }
        }
    }

}
