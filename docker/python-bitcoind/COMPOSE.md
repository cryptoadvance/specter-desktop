# docker-compose support

For an easy and fast way to run a full node with Specter and Tor on Linux, you can use [Docker Compose](https://docs.docker.com/compose/).

The compose file (`docker-compose.yml`) in this directory will both build the necessary components from source code and run them.

## Prerequisites

The following must be installed:

* Docker ([installation instructions](https://docs.docker.com/engine/install/#server))
* Docker Compose ([installation instructions](https://docs.docker.com/compose/install/))

## Running

Fastest:

`make up` - this will build and run all the components in the background and expose the specter port on the host machine.
