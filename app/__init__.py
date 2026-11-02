import os

from flask import Flask

from config import Config


def create_app(config_class=Config, **overrides):
    """Application factory. `overrides` replace config values (used by tests)."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    app.config.update(overrides)

    os.makedirs(app.instance_path, exist_ok=True)
    for key in ("DATABASE", "UPLOAD_FOLDER"):
        if not os.path.isabs(app.config[key]):
            app.config[key] = os.path.join(app.instance_path, app.config[key])

    from app.models.repositories import db
    db.init_app(app)

    from app.models.services.image_generator import create_image_generator
    app.extensions["image_generator"] = create_image_generator(app.config["IMAGE_GENERATOR"])

    from app.controllers import auth
    auth.init_app(app)

    from app.controllers.shop import bp as shop_bp
    from app.controllers.account import bp as account_bp
    from app.controllers.admin import bp as admin_bp
    app.register_blueprint(shop_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(admin_bp)

    return app
