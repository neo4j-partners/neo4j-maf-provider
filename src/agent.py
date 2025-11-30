"""
Agent management module using Microsoft Agent Framework with Azure AI Foundry.

This module provides configuration and agent creation using the Microsoft Agent
Framework (2025) with Azure AI Foundry (V2 SDK - azure-ai-projects) integration
for persistent, service-managed agents.
"""

import os

from agent_framework.azure import AzureAIClient
from azure.identity.aio import AzureCliCredential
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from logging_config import configure_logging

logger = configure_logging(os.getenv("APP_LOG_FILE", ""))


class AgentConfig(BaseSettings):
    """
    Agent configuration loaded from environment variables.

    Attributes:
        name: Name of the agent (AZURE_AI_AGENT_NAME)
        model: Model deployment name (AZURE_AI_MODEL_NAME)
        instructions: System instructions for the agent
        project_endpoint: Azure AI Foundry project endpoint (AZURE_AI_PROJECT_ENDPOINT)
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )

    name: str = Field(
        default="api-arches-agent",
        validation_alias="AZURE_AI_AGENT_NAME",
    )
    model: str = Field(
        default="gpt-4o",
        validation_alias="AZURE_AI_MODEL_NAME",
    )
    instructions: str = Field(
        default="You are a helpful API assistant.",
    )
    project_endpoint: str | None = Field(
        default=None,
        validation_alias="AZURE_AI_PROJECT_ENDPOINT",
    )


def create_agent_client(config: AgentConfig, credential: AzureCliCredential) -> AzureAIClient:
    """
    Create an AzureAIClient configured for Foundry.

    The returned client should be used as an async context manager to create agents.

    Args:
        config: Agent configuration with project endpoint and model settings.
        credential: Azure CLI credential for authentication.

    Returns:
        Configured AzureAIClient instance.
    """
    client_kwargs = {"async_credential": credential}

    if config.project_endpoint:
        client_kwargs["project_endpoint"] = config.project_endpoint

    if config.model:
        client_kwargs["model_deployment_name"] = config.model

    logger.info(f"Creating AzureAIClient for project: {config.project_endpoint}")
    return AzureAIClient(**client_kwargs)


def create_agent_context(client: AzureAIClient, config: AgentConfig):
    """
    Create an agent context manager from the client.

    Args:
        client: Configured AzureAIClient.
        config: Agent configuration with name and instructions.

    Returns:
        Async context manager that yields the agent.
    """
    logger.info(f"Creating agent '{config.name}' with model '{config.model}'...")
    return client.create_agent(
        name=config.name,
        instructions=config.instructions,
    )
