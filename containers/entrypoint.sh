#!/bin/bash

envsubst < /opt/models.json.template > /home/cad/.pi/agent/models.json
exec "$@"
