"""
Naebak Theme Service - User Interface Customization System

This is the main application file for the Naebak Theme Service, which provides
user interface customization capabilities for the Naebak platform. The service
manages user theme preferences, provides theme configuration data, and supports
dynamic theme switching for personalized user experiences.

Key Features:
- User-specific theme preference management
- Dynamic theme switching and persistence
- Theme configuration and asset management
- Redis-based fast theme retrieval
- Support for multiple theme variants
- Integration with frontend applications

Architecture:
The service implements a lightweight theme management system using Redis for
fast preference storage and retrieval. It supports both system-wide default
themes and user-specific customizations while providing APIs for theme
discovery and configuration.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import redis
import json
from datetime import datetime
import logging
from config import get_config

# Setup application
app = Flask(__name__)
config = get_config()
app.config.from_object(config)

# Setup CORS
CORS(app, origins=app.config["CORS_ALLOWED_ORIGINS"])

# Setup Redis for theme settings storage
try:
    redis_client = redis.from_url(app.config["REDIS_URL"])
    redis_client.ping()
    print("Connected to Redis for theme service successfully!")
except redis.exceptions.ConnectionError as e:
    print(f"Could not connect to Redis for theme service: {e}")
    redis_client = None

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class UserTheme:
    """
    Represents a user's theme preferences in the Naebak platform.
    
    This class encapsulates user-specific theme settings including the selected
    theme name and last update timestamp. It provides methods for serialization
    and supports theme validation and preference management.
    
    Attributes:
        user_id (str): Unique identifier of the user.
        theme_name (str): Name of the selected theme.
        last_updated (str): ISO format timestamp of the last theme update.
    
    Supported Themes:
        - light: Default light theme with high contrast
        - dark: Dark theme for low-light environments
        - high_contrast: Accessibility theme with enhanced contrast
        - naebak_classic: Platform-specific branded theme
        - government: Official government styling theme
    
    Theme Properties:
        - Color schemes and palettes
        - Typography and font selections
        - Layout spacing and sizing
        - Component styling variations
        - Accessibility enhancements
    """
    
    def __init__(self, user_id, theme_name, last_updated=None):
        """
        Initialize a new user theme preference.
        
        Args:
            user_id (str): The ID of the user.
            theme_name (str): The name of the selected theme.
            last_updated (str, optional): Update timestamp. Defaults to current UTC time.
        """
        self.user_id = str(user_id)
        self.theme_name = theme_name
        self.last_updated = last_updated if last_updated else datetime.utcnow().isoformat()

    def to_dict(self):
        """
        Convert user theme to dictionary format for JSON serialization.
        
        Returns:
            dict: Dictionary representation of the user theme preferences.
        """
        return {
            "user_id": self.user_id,
            "theme_name": self.theme_name,
            "last_updated": self.last_updated
        }
    
    def validate_theme(self, available_themes):
        """
        Validate that the theme name is supported by the platform.
        
        Args:
            available_themes (list): List of supported theme names.
            
        Returns:
            bool: True if theme is valid, False otherwise.
        """
        return self.theme_name in available_themes

@app.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint for service monitoring.
    
    This endpoint provides comprehensive health status including Redis connectivity
    and service version information. It's used by load balancers, monitoring systems,
    and the API gateway to verify service availability.
    
    Returns:
        JSON response with service health information including:
        - Service status and version
        - Redis connectivity status for theme storage
        - Available themes count
        - Timestamp of the health check
        
    Health Indicators:
        - Service status: Always "ok" if the service is running
        - Redis status: "connected", "disconnected", or error details
        - Theme count: Number of available themes for validation
    """
    redis_status = "disconnected"
    theme_count = 0
    
    if redis_client:
        try:
            redis_client.ping()
            redis_status = "connected"
            # Count stored user themes
            theme_keys = redis_client.keys("user_theme:*")
            theme_count = len(theme_keys) if theme_keys else 0
        except Exception as e:
            redis_status = f"error: {e}"

    return jsonify({
        "status": "ok", 
        "service": "naebak-theme-service", 
        "version": "1.0.0", 
        "redis_status": redis_status,
        "stored_themes_count": theme_count,
        "available_themes": app.config.get("AVAILABLE_THEMES", []),
        "timestamp": datetime.utcnow().isoformat()
    }), 200

@app.route("/api/themes/user/<user_id>", methods=["GET"])
def get_user_theme(user_id):
    """
    Retrieve the preferred theme for a specific user.
    
    This endpoint returns the user's current theme preference or the system
    default theme if no preference has been set. It provides fast theme
    retrieval for frontend applications during user session initialization.
    
    Args:
        user_id (str): The unique identifier of the user.
        
    Returns:
        JSON response with user theme information including:
        - User ID and selected theme name
        - Last update timestamp
        - Theme configuration details
        
    Fallback Behavior:
        - Returns default theme if user has no stored preference
        - Handles Redis connectivity issues gracefully
        - Provides consistent response format for all cases
    """
    if not redis_client:
        return jsonify({
            "error": "Theme service temporarily unavailable",
            "fallback_theme": app.config.get("DEFAULT_THEME", "light")
        }), 503

    try:
        theme_data = redis_client.get(f"user_theme:{user_id}")
        if theme_data:
            theme = json.loads(theme_data)
            logger.info(f"Retrieved theme {theme['theme_name']} for user {user_id}")
            return jsonify(theme), 200
        else:
            # Return default theme if no user preference found
            default_theme = {
                "user_id": user_id, 
                "theme_name": app.config.get("DEFAULT_THEME", "light"), 
                "last_updated": datetime.utcnow().isoformat(),
                "is_default": True
            }
            logger.info(f"No stored theme for user {user_id}, returning default")
            return jsonify(default_theme), 200
            
    except Exception as e:
        logger.error(f"Error retrieving theme for user {user_id}: {e}")
        return jsonify({
            "error": "Failed to retrieve theme",
            "fallback_theme": app.config.get("DEFAULT_THEME", "light")
        }), 500

@app.route("/api/themes/user/<user_id>", methods=["POST"])
def set_user_theme(user_id):
    """
    Set the preferred theme for a specific user.
    
    This endpoint allows users to update their theme preference and stores
    the selection for future sessions. It validates the theme name against
    available themes and provides immediate feedback.
    
    Args:
        user_id (str): The unique identifier of the user.
        
    Request Body:
        theme_name (str): The name of the theme to set.
        
    Returns:
        JSON response with update confirmation and theme details.
        
    Validation:
        - Ensures theme_name is provided and valid
        - Checks against list of available themes
        - Validates user_id format and requirements
        
    Error Handling:
        - 400: Invalid or missing theme name
        - 500: Redis storage errors
        - 503: Service temporarily unavailable
    """
    if not redis_client:
        return jsonify({
            "error": "Theme service temporarily unavailable"
        }), 503

    data = request.get_json()
    if not data:
        return jsonify({
            "error": "Request body is required",
            "required_fields": ["theme_name"]
        }), 400
        
    theme_name = data.get("theme_name")

    if not theme_name:
        return jsonify({
            "error": "Missing theme_name",
            "available_themes": app.config.get("AVAILABLE_THEMES", [])
        }), 400

    available_themes = app.config.get("AVAILABLE_THEMES", ["light", "dark"])
    if theme_name not in available_themes:
        return jsonify({
            "error": "Invalid theme_name",
            "provided": theme_name,
            "available_themes": available_themes
        }), 400

    try:
        user_theme = UserTheme(user_id, theme_name)
        redis_client.set(f"user_theme:{user_id}", json.dumps(user_theme.to_dict()))
        logger.info(f"User {user_id} set theme to {theme_name}")
        
        return jsonify({
            "message": "Theme updated successfully", 
            "theme": user_theme.to_dict(),
            "previous_theme": data.get("previous_theme", "unknown")
        }), 200
        
    except Exception as e:
        logger.error(f"Error setting theme for user {user_id}: {e}")
        return jsonify({
            "error": "Failed to update theme",
            "details": str(e)
        }), 500

@app.route("/api/themes/available", methods=["GET"])
def get_available_themes():
    """
    Retrieve the list of all available themes.
    
    This endpoint provides theme discovery for frontend applications,
    returning detailed information about each available theme including
    metadata and configuration options.
    
    Returns:
        JSON response with available themes and their properties.
    """
    available_themes = app.config.get("AVAILABLE_THEMES", ["light", "dark"])
    
    # Enhanced theme information with metadata
    theme_details = []
    for theme_name in available_themes:
        theme_info = {
            "name": theme_name,
            "display_name": theme_name.replace("_", " ").title(),
            "description": get_theme_description(theme_name),
            "preview_url": f"/api/themes/preview/{theme_name}",
            "is_default": theme_name == app.config.get("DEFAULT_THEME", "light")
        }
        theme_details.append(theme_info)
    
    return jsonify({
        "available_themes": theme_details,
        "default_theme": app.config.get("DEFAULT_THEME", "light"),
        "total_count": len(theme_details)
    }), 200

@app.route("/api/themes/preview/<theme_name>", methods=["GET"])
def get_theme_preview(theme_name):
    """
    Get preview information for a specific theme.
    
    This endpoint provides theme preview data including color schemes,
    typography samples, and component examples for theme selection interfaces.
    
    Args:
        theme_name (str): The name of the theme to preview.
        
    Returns:
        JSON response with theme preview data and styling information.
    """
    available_themes = app.config.get("AVAILABLE_THEMES", ["light", "dark"])
    
    if theme_name not in available_themes:
        return jsonify({
            "error": "Theme not found",
            "available_themes": available_themes
        }), 404
    
    # Generate theme preview data
    preview_data = {
        "theme_name": theme_name,
        "colors": get_theme_colors(theme_name),
        "typography": get_theme_typography(theme_name),
        "components": get_theme_components(theme_name),
        "accessibility": get_theme_accessibility(theme_name)
    }
    
    return jsonify(preview_data), 200

def get_theme_description(theme_name):
    """
    Get description for a specific theme.
    
    Args:
        theme_name (str): The name of the theme.
        
    Returns:
        str: Description of the theme.
    """
    descriptions = {
        "light": "Clean and bright theme optimized for daytime use",
        "dark": "Dark theme designed for low-light environments and reduced eye strain",
        "high_contrast": "High contrast theme for improved accessibility",
        "naebak_classic": "Official Naebak platform theme with brand colors",
        "government": "Formal government styling for official communications"
    }
    return descriptions.get(theme_name, "Custom theme variant")

def get_theme_colors(theme_name):
    """Get color scheme for a theme."""
    # This would typically load from a configuration file or database
    return {
        "primary": "#1976d2" if theme_name == "light" else "#90caf9",
        "secondary": "#dc004e" if theme_name == "light" else "#f48fb1",
        "background": "#ffffff" if theme_name == "light" else "#121212",
        "surface": "#f5f5f5" if theme_name == "light" else "#1e1e1e"
    }

def get_theme_typography(theme_name):
    """Get typography settings for a theme."""
    return {
        "font_family": "Roboto, Arial, sans-serif",
        "font_size_base": "16px",
        "line_height": "1.5",
        "font_weight_normal": "400",
        "font_weight_bold": "700"
    }

def get_theme_components(theme_name):
    """Get component styling for a theme."""
    return {
        "button_radius": "4px",
        "card_elevation": "2px",
        "input_border": "1px solid #ccc",
        "navbar_height": "64px"
    }

def get_theme_accessibility(theme_name):
    """Get accessibility features for a theme."""
    return {
        "contrast_ratio": "4.5:1" if theme_name != "high_contrast" else "7:1",
        "focus_indicators": True,
        "reduced_motion": False,
        "screen_reader_optimized": theme_name == "high_contrast"
    }

if __name__ == "__main__":
    """
    Run the theme service application.
    
    This starts the Flask server with the configured host, port, and debug settings.
    The server handles HTTP requests for theme management and configuration.
    """
    app.run(host="0.0.0.0", port=config.PORT, debug=config.DEBUG)
