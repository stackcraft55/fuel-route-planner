import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-local-development-key-change-me-in-production",
)
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "trip_planner",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "trip-planner",
        "TIMEOUT": 60 * 60 * 6,
        "OPTIONS": {"MAX_ENTRIES": 2000},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
# OSM tile servers reject requests without a Referer
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
}

TRIP_PLANNER = {
    "VEHICLE_RANGE_MILES": float(os.environ.get("VEHICLE_RANGE_MILES", 500)),
    "MILES_PER_GALLON": float(os.environ.get("MILES_PER_GALLON", 10)),
    # penalty per stop used only when choosing stops, not added to the cost
    "STOP_OVERHEAD_DOLLARS": float(os.environ.get("STOP_OVERHEAD_DOLLARS", 5)),
    # max distance from the route line
    "CORRIDOR_MILES": float(os.environ.get("CORRIDOR_MILES", 5)),
    "OSRM_URL": os.environ.get("OSRM_URL", "https://router.project-osrm.org"),
    "NOMINATIM_URL": os.environ.get("NOMINATIM_URL", "https://nominatim.openstreetmap.org"),
    "HTTP_USER_AGENT": os.environ.get("HTTP_USER_AGENT", "fuel-route-planner/1.0"),
    "HTTP_TIMEOUT_SECONDS": float(os.environ.get("HTTP_TIMEOUT_SECONDS", 20)),
    "FUEL_PRICES_CSV": DATA_DIR / "fuel-prices-for-be-assessment.csv",
    "PLACES_CSV": DATA_DIR / "us_places.csv",
    "CITY_LOOKUP_CSV": DATA_DIR / "city_lookup_extra.csv",
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"trip_planner": {"handlers": ["console"], "level": "INFO"}},
}
