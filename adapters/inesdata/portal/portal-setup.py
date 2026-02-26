import requests
import time
import secrets
import io
from datetime import datetime
from PIL import Image
import os

class PortalSetup:

    def __init__(self, config):
        self.backend_url = config["backend_url"].rstrip("/")
        self.admin_email = config["admin_email"]
        self.admin_password = config["admin_password"]

        self.admin_token = None
        self.api_token = None

    # --------------------------------------------------
    def log(self, message):
        print(f"[{datetime.utcnow().isoformat()}] {message}")

    # --------------------------------------------------
    def wait_for_backend(self, timeout=240):
        self.log("Waiting for Strapi backend...")
        start = time.time()

        while time.time() - start < timeout:
            try:
                r = requests.get(
                    f"{self.backend_url}/admin/init",
                    timeout=5
                )
                if r.status_code == 200:
                    self.log("Strapi backend ready")
                    return
            except Exception:
                pass
            time.sleep(3)

        raise Exception("Strapi backend timeout")

    # --------------------------------------------------
    def ensure_admin_exists(self):
        """Verifica si Strapi tiene administrador inicial. Si no, lo registra."""
        self.log("Checking if initial admin registration is required...")
        try:
            r = requests.get(f"{self.backend_url}/admin/init", timeout=5)
            data = r.json().get("data", {})
            
            if data.get("hasAdmin") is False:
                self.log("No admin detected. Registering initial administrator...")
                # Payload ultra-limpio para evitar ValidationError
                payload = {
                    "email": self.admin_email,
                    "password": self.admin_password,
                    "firstname": "Admin",
                    "lastname": "Pionera"
                }
                r_reg = requests.post(f"{self.backend_url}/admin/register-admin", json=payload, timeout=5)
                if r_reg.status_code in [200, 201]:
                    self.log("Initial admin registered successfully.")
                else:
                    raise Exception(f"Failed to register admin: {r_reg.text}")
            else:
                self.log("Admin account already exists. Proceeding to login.")
        except Exception as e:
            raise Exception(f"Error during admin check/registration: {str(e)}")

    # --------------------------------------------------
    def login_admin(self):
        self.log("Authenticating admin...")

        payload = {
            "email": self.admin_email,
            "password": self.admin_password
        }

        r = requests.post(
            f"{self.backend_url}/admin/login",
            json=payload,
            timeout=5
        )

        if r.status_code != 200:
            raise Exception(f"Admin login failed: {r.text}")

        self.admin_token = r.json()["data"]["token"]
        self.log("Admin authenticated")

    # --------------------------------------------------
    def create_api_token(self):
        self.log("Generating API Token...")

        headers = {
            "Authorization": f"Bearer {self.admin_token}"
        }

        token_name = f"Bootstrap_{secrets.token_hex(4)}"

        payload = {
            "name": token_name,
            "description": "Bootstrap automation token",
            "type": "full-access",
            "lifespan": None
        }

        r = requests.post(
            f"{self.backend_url}/admin/api-tokens",
            headers=headers,
            json=payload
        )

        if r.status_code not in [200, 201]:
            raise Exception(f"Failed to create API Token: {r.text}")

        self.api_token = r.json()["data"]["accessKey"]
        self.log(f"API Token generated: {token_name}")
        self.log(f"TOKEN KEY: {self.api_token}")

    # --------------------------------------------------
    def generate_placeholder_image(self, size=(800, 400), color=(30, 60, 120)):
        img = Image.new("RGB", size, color=color)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    # --------------------------------------------------
    def upload_image(self, image_buffer, filename):
        headers = {
            "Authorization": f"Bearer {self.api_token}"
        }

        files = {
            "files": (filename, image_buffer, "image/png")
        }

        r = requests.post(
            f"{self.backend_url}/api/upload",
            headers=headers,
            files=files
        )

        if r.status_code not in [200, 201]:
            raise Exception(f"Image upload failed: {r.text}")

        image_id = r.json()[0]["id"]
        return image_id

    # --------------------------------------------------
    def ensure_landing_page(self):
        self.log("Generando imágenes claras para máxima legibilidad...")
        ultra_light_grey = (245, 245, 245)

        welcome_img = self.upload_image(self.generate_placeholder_image(color=ultra_light_grey), "welcome.png")
        catalog_img = self.upload_image(self.generate_placeholder_image(color=ultra_light_grey), "catalog.png")
        about_img = self.upload_image(self.generate_placeholder_image(color=ultra_light_grey), "about.png")
        join_img = self.upload_image(self.generate_placeholder_image(color=ultra_light_grey), "join.png")

        self.log("Actualizando Landing Page...")
        headers = {"Authorization": f"Bearer {self.api_token}"}
        
        payload = {
            "data": {
                "Title": "INESData Dataspace",
                "Welcome": {"Text": "Welcome to the INESData Dataspace Portal", "Image": welcome_img},
                "Catalog": {
                    "Title": "Explore the Dataspace Catalog",
                    "Description": "Access available datasets and services.",
                    "Background": catalog_img
                },
                "GetToKnowUs": {
                    "Title": "About INESData",
                    "Description": "INESData is a federated dataspace infrastructure.",
                    "Background": about_img
                },
                "Join": {
                    "Title": "Join the Dataspace",
                    "Description": "Become a participant in the INESData ecosystem.",
                    "Image": join_img
                },
                "publishedAt": datetime.utcnow().isoformat()
            }
        }

        r = requests.put(f"{self.backend_url}/api/landing-page", headers=headers, json=payload)
        if r.status_code not in [200, 201]:
            raise Exception(f"Error al actualizar: {r.text}")
        self.log("Landing Page restaurada con fondo claro y texto legible.")

    # --------------------------------------------------
    def configure_public_permissions(self):
        self.log("Configuring Public role permissions (Smart Match)...")
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        role_id = 2 
        path = f"{self.backend_url}/users-permissions/roles/{role_id}"
        
        r = requests.get(path, headers=headers)
        if r.status_code != 200:
            path = f"{self.backend_url}/admin/users-permissions/roles/{role_id}"
            r = requests.get(path, headers=headers)

        if r.status_code != 200:
            self.log("Error: Could not fetch role details.")
            return

        role_data = r.json().get("role", r.json().get("data", r.json()))
        permissions = role_data["permissions"]

        def smart_enable(search_term, action):
            found = False
            for uid in permissions.keys():
                if search_term.lower() in uid.lower():
                    controllers = permissions[uid].get("controllers", {})
                    for ctrl_name in controllers.keys():
                        if action in controllers[ctrl_name]:
                            controllers[ctrl_name][action]["enabled"] = True
                            self.log(f" [OK] Enabled: {uid} -> {ctrl_name} -> {action}")
                            found = True
            if not found:
                self.log(f" [!] Could not find permission for: {search_term} ({action})")

        targets = [
            ("landing-page", "find"),
            ("get-federated-catalog", "getFederatedCatalog"),
            ("get-vocabularies", "getVocabularies"),
            ("generic-page", "find"),
            ("generic-page", "findOne"),
            ("menu", "find"),
            ("menu", "findOne")
        ]

        for resource, action in targets:
            smart_enable(resource, action)

        update_r = requests.put(path, headers=headers, json={"permissions": permissions})
        if update_r.status_code == 200:
            self.log("Public permissions updated successfully!")
        else:
            self.log(f"Update failed: {update_r.text}")

    # --------------------------------------------------
    def ensure_menu_exists(self):
        self.log("Ensuring 'public-portal-menu' exists...")
        headers = {"Authorization": f"Bearer {self.api_token}"}

        check_url = f"{self.backend_url}/api/menus?filters[slug][$eq]=public-portal-menu"
        r_check = requests.get(check_url, headers=headers)
        
        if r_check.status_code == 200:
            data = r_check.json().get("data", [])
            if data:
                self.log("Menu 'public-portal-menu' already exists. Skipping creation.")
                return

        payload = {
            "data": {
                "title": "public-portal-menu",
                "slug": "public-portal-menu"
            }
        }
        
        r_create = requests.post(f"{self.backend_url}/api/menus", headers=headers, json=payload)
        
        if r_create.status_code in [200, 201]:
            self.log("Menu 'public-portal-menu' created successfully.")
        else:
            self.log(f"Failed to create menu: {r_create.text}")

    # --------------------------------------------------
    def run(self):
        self.wait_for_backend()
        self.ensure_admin_exists()  # <-- Ahora registra si es necesario
        self.login_admin()          # <-- Ahora ya puede loguearse siempre
        self.create_api_token()
        self.ensure_landing_page()
        self.configure_public_permissions()
        self.ensure_menu_exists()
        self.log("Portal bootstrap completed successfully.")


# --------------------------------------------------
# EXECUTION
# --------------------------------------------------

import os

if __name__ == "__main__":

    # Permite sobreescribir dinámicamente el backend desde Nivel 10
    backend_url = os.environ.get(
        "PORTAL_BACKEND_URL",
        "http://backend-demo.dev.ds.inesdata.upm"
    )

    config = {
        "backend_url": backend_url,
        "admin_email": "admin@pionera.local",
        "admin_password": "Admin123!"
    }

    print(f"🔗 Backend URL: {backend_url}")

    setup = PortalSetup(config)

    try:
        setup.run()
    except Exception as e:
        print(f"❌ Portal bootstrap failed: {e}")
        raise