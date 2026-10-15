from flask import Flask, request, jsonify

app = Flask(__name__)

countries = [
    {"id": 1, "name": "United States", "code": "US"},
    {"id": 2, "name": "Canada", "code": "CA"},
    {"id": 3, "name": "United Kingdom", "code": "GB"},
]

def _find_net_id():
    return max(country["id"] for country in countries) + 1 

@app.get("/countries")
def get_countries():
    return jsonify(countries)

@app.post("/countries")
def add_country():
    if request.is_json:
        country = request.get_json()
        country["id"] = _find_net_id()
        countries.append(country)
        return jsonify(country), 201
    return jsonify({"error": "Request must be JSON"}), 415
        