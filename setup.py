from setuptools import setup, find_packages

setup(
    name="workflow-agent",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "pyyaml>=6.0",
        "pydantic>=2.0",
        "jinja2>=3.0",
        "aiohttp>=3.8",
        "python-dotenv>=1.0"
    ],
    extras_require={
        "llm": [
            "langchain>=0.1.0",
            "openai>=1.0.0",
            "google-generativeai>=0.3.0"
        ],
        "dev": [
            "pytest>=7.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0",
            "isort>=5.0",
            "mypy>=1.0"
        ]
    },
    python_requires=">=3.8",
    description="Workflow Agent for managing infrastructure and integrations",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/workflow-agent",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)