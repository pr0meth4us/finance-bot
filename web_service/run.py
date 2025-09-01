from app import create_app

app = create_app()

if __name__ == '__main__':
    # Use host='0.0.0.0' to be accessible within a Docker container or network
    app.run(host='0.0.0.0', port=8000)