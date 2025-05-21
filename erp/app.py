import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity, get_jwt
)
from dotenv import load_dotenv

load_dotenv()

app = Flask(
    __name__,
    static_folder='static',
    static_url_path=''
)
CORS(app)

# MySQL config
app.config['MYSQL_HOST']     = os.getenv('MYSQL_HOST', 'localhost')
app.config['MYSQL_USER']     = os.getenv('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD', 'dev123')
app.config['MYSQL_DB']       = os.getenv('MYSQL_DATABASE', 'prosdesDB')

# JWT config
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET', 'devsecret')

mysql  = MySQL(app)
bcrypt = Bcrypt(app)
jwt    = JWTManager(app)

# Serve static files
@app.route('/', defaults={'path': 'index.html'})
@app.route('/<path:path>')
def serve_frontend(path):
    if os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/health')
def health():
    return jsonify({"status": "OK"}), 200

#
# Auth Endpoints
#
@app.route('/api/auth/register', methods=['POST'])
def register():
    data   = request.get_json()
    hashed = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    cursor = mysql.connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO users (name, email, password, role)
            VALUES (%s, %s, %s, %s)
            """,
            (data['name'], data['email'], hashed, data.get('role', 'employee'))
        )
        mysql.connection.commit()
        return '', 201
    except Exception as e:
        msg = str(e)
        if "Duplicate entry" in msg and "for key 'email'" in msg:
            return jsonify(error="Email already registered."), 400
        return jsonify(error=msg), 400
    finally:
        cursor.close()

@app.route('/api/auth/login', methods=['POST'])
def login():
    data   = request.get_json()
    cursor = mysql.connection.cursor()
    cursor.execute(
        "SELECT id, name, email, password, role FROM users WHERE email = %s",
        (data['email'],)
    )
    user = cursor.fetchone()
    cursor.close()

    # Check credentials
    if user and bcrypt.check_password_hash(user[3], data['password']):
        # Make subject a string (required by flask_jwt_extended)
        token = create_access_token(
            identity=str(user[0]),
            additional_claims={
                'role':  user[4],
                'email': user[2]
            }
        )
        return jsonify({
            'token': token,
            'user': {
                'id':   user[0],
                'name': user[1],
                'role': user[4],
                'email': user[2]
            }
        })

    return jsonify(error='Invalid credentials'), 401

#
# Queries Endpoints
#
@app.route('/api/queries', methods=['GET'])
@jwt_required()
def get_queries():
    # Retrieve user ID from the token subject
    user_id = int(get_jwt_identity())
    cursor = mysql.connection.cursor()
    cursor.execute(
        """
        SELECT id, created_at, client_name, client_type, location,
               area_sqft, specification, proposed_amount, final_amount, status
          FROM queries
         WHERE user_id = %s
        """,
        (user_id,)
    )
    cols = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    cursor.close()

    queries = [dict(zip(cols, row)) for row in rows]
    return jsonify(queries)

@app.route('/api/queries', methods=['POST'])
@jwt_required()
def add_query():
    user_id = int(get_jwt_identity())
    data    = request.get_json() or {}
    cursor  = mysql.connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO queries
              (user_id, client_name, client_type, location,
               area_sqft, specification, proposed_amount, final_amount, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                data.get('clientName'),
                data.get('clientType'),
                data.get('location'),
                data.get('areaSqft'),
                data.get('specification', ''),
                data.get('proposedAmount'),
                data.get('finalAmount'),
                data.get('status', 'Ongoing')
            )
        )
        mysql.connection.commit()
        return '', 201
    except Exception as e:
        mysql.connection.rollback()
        return jsonify(error=str(e)), 500
    finally:
        cursor.close()

@app.route('/api/queries/<int:query_id>', methods=['PUT'])
@jwt_required()
def update_query(query_id):
    user_id = int(get_jwt_identity())
    data    = request.get_json() or {}
    
    cursor = mysql.connection.cursor()
    try:
        # Build the update query dynamically based on the fields provided
        fields_to_update = []
        values = []
        
        # Check each field that can be updated
        if 'clientName' in data:
            fields_to_update.append("client_name = %s")
            values.append(data['clientName'])
        
        if 'clientType' in data:
            fields_to_update.append("client_type = %s")
            values.append(data['clientType'])
            
        if 'location' in data:
            fields_to_update.append("location = %s")
            values.append(data['location'])
            
        if 'areaSqft' in data:
            fields_to_update.append("area_sqft = %s")
            values.append(data['areaSqft'])
            
        if 'specification' in data:
            fields_to_update.append("specification = %s")
            values.append(data['specification'])
            
        if 'proposedAmount' in data:
            fields_to_update.append("proposed_amount = %s")
            values.append(data['proposedAmount'])
            
        if 'finalAmount' in data:
            fields_to_update.append("final_amount = %s")
            values.append(data['finalAmount'])
            
        if 'status' in data:
            fields_to_update.append("status = %s")
            values.append(data['status'])
        
        # If there's nothing to update, return error
        if not fields_to_update:
            return jsonify(error="Nothing to update"), 400
            
        # Build the SQL query
        sql = "UPDATE queries SET " + ", ".join(fields_to_update) + " WHERE id = %s AND user_id = %s"
        values.append(query_id)
        values.append(user_id)
        
        cursor.execute(sql, tuple(values))
        mysql.connection.commit()
        
        # Check if any rows were affected
        if cursor.rowcount == 0:
            return jsonify(error="Query not found or you don't have permission to update it"), 404
            
        return '', 200
    except Exception as e:
        mysql.connection.rollback()
        return jsonify(error=str(e)), 500
    finally:
        cursor.close()

@app.route('/api/queries/<int:query_id>/status', methods=['PATCH'])
@jwt_required()
def update_query_status(query_id):
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}
    
    if 'status' not in data:
        return jsonify(error="Status is required"), 400
        
    # Validate the status value
    valid_statuses = ['Ongoing', 'Approved', 'Closed']
    if data['status'] not in valid_statuses:
        return jsonify(error=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"), 400
    
    cursor = mysql.connection.cursor()
    try:
        cursor.execute(
            """
            UPDATE queries
               SET status = %s
             WHERE id = %s AND user_id = %s
            """,
            (data['status'], query_id, user_id)
        )
        mysql.connection.commit()
        
        if cursor.rowcount == 0:
            return jsonify(error="Query not found or you don't have permission to update it"), 404
            
        return '', 200
    except Exception as e:
        mysql.connection.rollback()
        return jsonify(error=str(e)), 500
    finally:
        cursor.close()

@app.route('/api/queries/<int:query_id>', methods=['GET'])
@jwt_required()
def get_query(query_id):
    user_id = int(get_jwt_identity())
    cursor = mysql.connection.cursor()
    
    try:
        cursor.execute(
            """
            SELECT id, created_at, client_name, client_type, location,
                   area_sqft, specification, proposed_amount, final_amount, status
              FROM queries
             WHERE id = %s AND user_id = %s
            """,
            (query_id, user_id)
        )
        
        cols = [d[0] for d in cursor.description]
        row = cursor.fetchone()
        
        if not row:
            return jsonify(error="Query not found"), 404
            
        query = dict(zip(cols, row))
        return jsonify(query)
    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        cursor.close()

@app.route('/api/me', methods=['GET'])
@jwt_required()
def get_me():
    # Expose the standard subject + custom claims
    raw_sub = get_jwt_identity()
    claims  = get_jwt()
    return jsonify({
        'id':    int(raw_sub),
        'role':  claims.get('role'),
        'email': claims.get('email')
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)