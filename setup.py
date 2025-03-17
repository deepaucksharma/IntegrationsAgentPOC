from setuptools import setup, find_packages

setup(
    name="workflow-agent",
    version="0.2.0",
    description="A Python framework for orchestrating multi-step workflows with AI-driven adaptation.",
    author="Your Name",
    author_email="you@example.com",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "jinja2==3.1.2",
        "typer==0.9.0",
        "rich==13.3.2",
        "InquirerPy==0.3.4",
        "python-dotenv==1.0.0",
        "PyYAML==6.0",
        "SQLAlchemy==1.4.47",
        "psutil==5.9.5",
        "pydantic==1.10.7",
        "asyncio==3.4.3",
        "aiosqlite==0.17.0",
        "aiohttp==3.8.5",
        "pytest==7.3.1",
        "pytest-asyncio==0.21.0",
        # Optional dependencies
        "shellcheck-py==0.9.0",  # For script validation
        "asyncpg",               # For PostgreSQL async support
        "aiomysql",              # For MySQL async support
    ],
    extras_require={
        "llm": ["langchain-openai==0.0.1"],  # For LLM optimization
        "doc": ["sphinx", "sphinx-rtd-theme"],  # For building documentation
        "dev": ["black", "isort", "pylint", "mypy"],  # For development
    },
    entry_points={
        "console_scripts": [
            "workflow-agent=workflow_agent.cli.main:app",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)