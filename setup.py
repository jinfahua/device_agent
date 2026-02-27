"""
Setup script for Device Agent.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="device-agent",
    version="0.1.0",
    author="Device Agent Team",
    description="A lightweight IoT device management agent",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "paho-mqtt>=1.6.0",
        "pyyaml>=6.0",
    ],
    extras_require={
        "anthropic": ["anthropic>=0.20.0"],
        "openai": ["openai>=1.0.0"],
        "dev": ["pytest>=7.0", "pytest-asyncio>=0.21.0", "black", "mypy"],
        "all": [
            "anthropic>=0.20.0",
            "openai>=1.0.0",
            "pytest>=7.0",
            "pytest-asyncio>=0.21.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "device-agent=device_agent.standalone.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
