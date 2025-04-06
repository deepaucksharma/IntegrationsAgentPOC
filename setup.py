from setuptools import setup, find_packages

setup(
    name="workflow-agent",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "jinja2>=3.1.2",
        "typer>=0.9.0",
        "pyyaml>=6.0",
        "pydantic>=2.0.0,<3.0.0",
        "typing-extensions>=4.0.0",
        "aiohttp>=3.8.0",
        "requests>=2.28.0", 
        "psutil>=5.9.5",
        "aiofiles>=22.1.0",
        "shellcheck-py>=0.9.0.6",
        "python-dotenv>=1.0.0",
        "beautifulsoup4>=4.9.3",
        "lxml>=4.9.0"
    ],
    extras_require={
        "llm": [
            "langchain>=0.1.0",
            "openai>=1.0.0",
            "google-generativeai>=0.3.0",
            "tavily-python>=0.2.0"
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
    author="Your Organization",
    author_email="example@example.com",
    url="https://github.com/example/workflow-agent",
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
