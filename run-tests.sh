#!/bin/bash -e

REST_CONFIG=./rest-service/tox.ini
WORKFLOWS_CONFIG=./workflows/tox.ini

install_dependencies() {
    echo "### Installing dependencies..."
    case $CIRCLE_NODE_INDEX in
        0)
            tox -c $REST_CONFIG -e clientV1-endpoints --notest
            tox -c $REST_CONFIG -e clientV1-infrastructure --notest
            ;;
        1)
            tox -c $REST_CONFIG -e clientV2-endpoints --notest
            pip install flake8
            ;;
        2)
            tox -c $REST_CONFIG -e clientV2-infrastructure --notest
            tox -c $WORKFLOWS_CONFIG --notest
            ;;
        3)
            tox -c $REST_CONFIG -e clientV2_1-endpoints --notest
            ;;
        4)
            tox -c $REST_CONFIG -e clientV2_1-infrastructure --notest
            ;;
        5)
            tox -c $REST_CONFIG -e clientV3-endpoints --notest
            ;;
        6)
            tox -c $REST_CONFIG -e clientV3-infrastructure --notest
            ;;
    esac
}

run() {
    echo "### Running tests..."
    case $CIRCLE_NODE_INDEX in
        0)
            tox -c $REST_CONFIG -e clientV1-endpoints
            tox -c $REST_CONFIG -e clientV1-infrastructure
            ;;
        1)
            tox -c $REST_CONFIG -e clientV2-endpoints
            flake8 plugins/riemann-controller/ workflows/ rest-service/ tests/
            ;;
        2)
            tox -c $REST_CONFIG -e clientV2-infrastructure
            tox -c $WORKFLOWS_CONFIG
            ;;
        3)
            tox -c $REST_CONFIG -e clientV2_1-endpoints
            ;;
        4)
            tox -c $REST_CONFIG -e clientV2_1-infrastructure
            ;;
        5)
            tox -c $REST_CONFIG -e clientV3-endpoints
            ;;
        6)
            tox -c $REST_CONFIG -e clientV3-infrastructure
            ;;
    esac
}

case $1 in
    --install-dependencies)
        install_dependencies
        ;;
    *)
        run
        ;;
esac
