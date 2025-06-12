from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="gcp-pubsub-events",
    version="1.0.1",
    author="Your Name",
    author_email="shadowrhyder@gmail.com",
    description="A decorator-based library for handling Google Cloud Pub/Sub messages with FastAPI integration, inspired by Micronaut's @PubSubListener",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Executioner1939/gcp-pubsub-events",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Distributed Computing",
    ],
    python_requires=">=3.7",
    install_requires=[
        "google-cloud-pubsub>=2.0.0",
        "pydantic>=2.0.0",
        "six>=1.16.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-asyncio>=0.18.0",
            "pytest-cov>=4.0.0",
            "pytest-timeout>=2.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
        ],
    },
)