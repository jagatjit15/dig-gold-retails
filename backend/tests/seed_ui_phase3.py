# Seeds fresh items for phase-3 UI tests (transfer x2, billing x1, lookbook x2 with one photo)
import io, os, uuid, requests
from PIL import Image, ImageDraw
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
h = {"Cookie": "swarna_access=" + requests.post(f"{API}/auth/login", json={"email": "admin@swarnaerp.in", "password": "Admin@12345"}).cookies["swarna_access"]}
br = {b["code"]: b["id"] for b in requests.get(f"{API}/branches", headers=h).json()}
pur = {p["code"]: p["id"] for p in requests.get(f"{API}/purities", headers=h).json()}
cat = requests.get(f"{API}/categories", headers=h).json()[0]["id"]
run = uuid.uuid4().hex[:4].upper()
out = {}
for k, desc in [("tr1", "UI Transfer A"), ("tr2", "UI Transfer B"), ("bill", "UI Bill Ring"), ("lb1", "Ruby Choker"), ("lb2", "Kundan Bangle Set Extra Long Name")]:
    r = requests.post(f"{API}/items", headers=h, json={"tag_id": f"UI{run}-{k.upper()}", "category_id": cat, "purity_id": pur["22K916"],
                      "gross_wt": 15.5, "stone_wt": 0.75, "making_charge_type": "per_gram", "making_charge_value": 450,
                      "branch_id": br["ZB-MAIN"], "description": desc})
    r.raise_for_status(); out[k] = r.json()
img = Image.new("RGB", (800, 800), "#8B0000"); ImageDraw.Draw(img).ellipse([150, 150, 650, 650], fill="#FFD700")
buf = io.BytesIO(); img.save(buf, "JPEG")
r = requests.post(f"{API}/files", headers=h, data={"owner_type": "item", "owner_id": out["lb1"]["id"], "category": "photo"},
                  files={"file": ("ruby.jpg", buf.getvalue(), "image/jpeg")})
print("upload", r.status_code)
for k, v in out.items():
    print(k, v["tag_id"], v["id"])
