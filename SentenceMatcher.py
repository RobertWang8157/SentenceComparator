import random
from http.server import BaseHTTPRequestHandler, HTTPServer
from sentence_transformers import SentenceTransformer, util
import mysql.connector
import json
import torch


def connect_to_database():
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="3659215fF",
        database="handle_together"
    )
    return connection


def send_json_response(self, status_code, data):
    # Convert status_code to integer
    status_code = int(status_code)

    # Set up the HTTP response
    self.send_response(status_code)
    self.send_header("Content-type", "application/json")
    self.end_headers()

    # Convert the data to JSON
    json_response = json.dumps(data)

    # Send the JSON response
    self.wfile.write(json_response.encode('utf-8'))


class WebServerHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        # Read the content length from the request headers
        content_length = int(self.headers['Content-Length'])

        # Read the JSON data from the request body
        post_data = self.rfile.read(content_length)
        json_data_list = json.loads(post_data.decode('utf-8'))

        if json_data_list:
            json_data = json_data_list[0]
            # Now json_data contains the parameters sent in the JSON format
            tag_array = json_data.get('tag_array', [])
            subject_array = json_data.get('subject_array', [])
            object_array = json_data.get('object_array', [])
            input_sentence = json_data.get('input_sentence', '')
            public_ind = json_data.get('public_ind', '')
            command_ind = json_data.get('command_ind', '')

        # Load the Sentence Transformer model
        # model = SentenceTransformer("shibing624/text2vec-base-chinese")
        model = SentenceTransformer("paraphrase-MiniLM-L6-v2")

        # Fetch distinct subject codes from intent_type table
        connection = connect_to_database()
        cursor = connection.cursor()

        # Use parameterized query to avoid SQL injection
        if tag_array and any(tag_array):
            tag_condition = "tag IN ({})".format(','.join(['%s' for _ in tag_array]))
        else:
            tag_condition = "1=1"  # Always true if tag_array is empty or None

        if command_ind:
            tag_condition2 = "AND COMMAND_IND = '" + command_ind + "'"
        else:
            tag_condition2 = ""

        query = (
                    "SELECT tag, content, subject FROM intent_training_data WHERE {} AND subject IN ({}) AND object IN ({}) AND PUBLIC_IND = '" + public_ind + "'" + tag_condition2).format(
            tag_condition, ','.join(['%s' for _ in subject_array]), ','.join(['%s' for _ in object_array]))
        params = tag_array + subject_array + object_array
        cursor.execute(query, params)
        rows = cursor.fetchall()
        candidate_responses_tags = [row[0] for row in rows]
        candidate_responses = [row[1] for row in rows]
        candidate_responses_subject = [row[2] for row in rows]
        cursor.close()
        connection.close()
        print('1')
        # Handle the case when no candidate responses are found
        if not candidate_responses:
            print('2')

            result = {
                "input_sentence": input_sentence,
                "tag": "",
                "content": "😊",
                "sim_content": "",
                "similarity": 0.0,
                "subject": ""
            }
            send_json_response(self, '200', result)
            return

        # Encode input sentence and candidate responses
        input_embedding = model.encode([input_sentence])
        response_embeddings = model.encode(candidate_responses)

        # Calculate cosine similarity between input and responses
        similarities = util.pytorch_cos_sim(input_embedding, response_embeddings)[0]

        most_similar_index = similarities.argmax().item()
        top_n_indices = torch.argsort(similarities, descending=True)[:5]

        # Randomly select 1 response from the top 5
        selected_index = random.choice(top_n_indices)
        selected_response_tag = candidate_responses_tags[selected_index]
        selected_response = candidate_responses[selected_index]
        selected_response_embedding = model.encode([selected_response])
        similarity = util.pytorch_cos_sim(input_embedding, selected_response_embedding)

        # Print the selected response
        print("Selected Response:", selected_response)
        # Print the most similar response
        print("Input sentence:", input_sentence)
        print("Most tag:", candidate_responses_tags[most_similar_index])
        print("Most similar response:", candidate_responses[most_similar_index])
        print("subject response:", candidate_responses_subject[most_similar_index])

        print("similarity:", similarity)
        result = {
            "input_sentence": input_sentence,
            "tag": candidate_responses_tags[most_similar_index],
            "content": selected_response,
            "sim_content": candidate_responses[most_similar_index],
            "similarity": round(similarity.item(), 5),
            "subject": candidate_responses_subject[most_similar_index]
        }
        send_json_response(self, '200', result)


if __name__ == '__main__':
    try:
        port = 8000
        server = HTTPServer(('localhost', port), WebServerHandler)
        server.max_body_length = 10 * 1024 * 1024  # set to 10 MB

        print(f'Server running on port {port}')

        server.serve_forever()
    except KeyboardInterrupt:
        print('^C received, shutting down server')
        server.socket.close()