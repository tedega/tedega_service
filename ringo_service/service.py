#!/usr/bin/env python3
import sys
import os
import logging
import connexion
from connexion import NoContent

from db import get_engine, get_session
from model.item import (
    create_model,
    load_items,
    load_item,
    create_item
)

from model.converters import (
    from_json,
    to_json
)

from lib.swagger import (
    generate_config,
    write_config
)


SERVICE_CONFIG = "SERVICE_CONFIG"
"""Name of the environment valirable which stores the path to the custom
service configuration. See
http://flask.pocoo.org/docs/dev/config/#configuring-from-files
"""
SERVICE_MODE = "SERVICE_MODE"
"""Name of the environment valirable which stores mode of the
application. The following modes are available:
1. Development
2. Production
"""

# Create a new logger for this service.
logger = logging.getLogger(__name__)


connexion_app = connexion.App(__name__)
app = connexion_app.app
config = app.config
config.from_object('ringo_service.config.{}Config'.format(os.environ.get(SERVICE_MODE, "Development")))
if os.environ.get(SERVICE_CONFIG):
    config.from_envvar(SERVICE_CONFIG)

db = get_session(config.get('DATABASE_URI'))


def get_items(limit):
    return [to_json(item.values) for item in load_items(db)][:limit]


def get_item(item_id):
    item = load_item(db, item_id)
    if item:
        return to_json(item.values) 
    return NoContent, 404


def put_item(item_id, item):
    loaded_item = load_item(db, item_id)
    if loaded_item:
        try:
            loaded_item.set_values(from_json(item))
            db.commit()
            logger.info('Updating item %s..', item_id)
            return NoContent, 200
        except Exception:
            logger.error('Failed updating item %s..', item_id)
            db.rollback()
            raise
    else:
        try:
            new_item = create_item(from_json(item))
            db.add(new_item)
            db.commit()
            logger.info('Creating item %s..', item_id)
            return NoContent, 201
        except Exception:
            logger.error('Failed creating item %s..', item_id)
            db.rollback()
            raise


def delete_item(item_id):
    loaded_item = load_item(db, item_id)
    if loaded_item:
        try:
            db.delete(loaded_item)
            db.commit()
            logger.info('Deleting item %s..', item_id)
            return NoContent, 204
        except Exception:
            db.rollback()
            logger.error('Failed deleting item %s..', item_id)
            raise
    else:
        return None

if __name__ == '__main__':
    # Load configuration
    engine = get_engine(app.config.get("DATABASE_URI"))
    domain_model = app.config.get("DOMAIN_MODEL")
    # Setup Logging
    if config.get("DEBUG"):
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if not domain_model:
        print("Error. No domain model is configured.")
        sys.exit(1)
    model = create_model(engine, domain_model)

    # Generate the config file
    swagger_config = generate_config(config.get('API_CONFIG'), model)
    with write_config(swagger_config) as swagger_config_file:
        connexion_app.add_api(swagger_config_file)

    connexion_app.run(port=config.get('SERVER_PORT'),
                      server=config.get('SERVER'))
