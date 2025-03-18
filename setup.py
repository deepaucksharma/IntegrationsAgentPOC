from setuptools import setup, find_packages

setup(
    name="workflow-agent",
    version="0.1.0",
    description="A Python framework for orchestrating multi-step workflows with AI-driven adaptation.",
    author="Your Name",
    author_email="you@example.com",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "jinja2>=3.1.2",
        "typer>=0.9.0",
        "PyYAML>=6.0",
        "psutil>=5.9.5",
    ],
    extras_require={
        "llm": ["langchain-openai>=0.0.1"],
        "doc": ["sphinx", "sphinx-rtd-theme"],
        "dev": [
            "black",
            "isort",
            "pylint",
            "mypy",
            "shellcheck-py>=0.9.0.6"
        ],
    },
    # Removed console entry point referencing non-existent module.
    entry_points={},
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