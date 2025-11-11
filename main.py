import os
import io
from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd
from google.cloud import storage

app = Flask(__name__)
CORS(app)

BUCKET_NAME = "smart-dental-datasets"
BLOB_NAME = "d_lab_400.csv"

if not BUCKET_NAME or not BLOB_NAME:
    print("FATAL: Please set the BUCKET_NAME and BLOB_NAME environment variables.")


def retrieve_and_process_csv(lab_id):
    if not BUCKET_NAME or not BLOB_NAME:
         return None, "Server configuration error: BUCKET_NAME or BLOB_NAME not set.", 500

    try:

        client = storage.Client()
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(BLOB_NAME)

        if not blob.exists():
            return None, f"File not found in bucket: gs://{BUCKET_NAME}/{BLOB_NAME}", 404

        csv_bytes = blob.download_as_bytes()
        csv_string = csv_bytes.decode('utf-8')
        
        csv_file_like = io.StringIO(csv_string)

        df = pd.read_csv(csv_file_like)
        
        try:
            filtered = df[df['LAB_ID']==lab_id]
        except KeyError:
            return None, "Data associated to LAB_ID not found in the registry.", 400
        if filtered.empty:
            return None, "No records found.", 404

        data_list = filtered.to_dict('records')
        return data_list, None, 200

    except Exception as e:
        app.logger.error(f"Error processing GCS data: {e}")
        return None, f"An unexpected server error occurred: {str(e)}", 500

@app.route('/data', methods=['POST'])
def get_data_from_gcs():

    req_data = request.get_json()
    if not req_data or 'LAB_ID' not in req_data:
        return jsonify({"error": "Missing 'LAB_ID' in request JSON."}), 400
    
    lab_id = req_data['LAB_ID']
    data, error_msg, status_code = retrieve_and_process_csv(lab_id=lab_id)

    if data is not None:

        return jsonify({
            "message": f"Successfully retrieved data from gs://{BUCKET_NAME}/{BLOB_NAME}",
            "data": data
        }), status_code
    else:
        return jsonify({"error": error_msg}), status_code

@app.route('/', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    return jsonify({"status": "ok", "service": "GCS CSV API"}), 200

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5051)))