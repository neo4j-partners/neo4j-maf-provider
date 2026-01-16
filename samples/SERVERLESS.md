# Serverless Models Proposal

This proposal outlines how Azure AI Foundry serverless models could simplify the samples setup by eliminating the need to deploy dedicated Azure infrastructure.

## Current Setup Problem

Today, running the samples requires:

1. Running `azd up` to deploy Azure infrastructure
2. Waiting for provisioning of AI Services, Storage, Log Analytics, Application Insights
3. Setting up role assignments and permissions
4. Running `setup_env.py` to sync environment variables

This creates friction for users who just want to quickly try the Neo4j context provider demos. The infrastructure deployment takes time, costs money even when idle, and requires cleanup afterward.

## What Are Serverless Models?

Azure AI Foundry offers "Models as a Service" (MaaS) - a way to consume AI models via API without hosting them on your own subscription. Key characteristics:

- **No infrastructure to manage**: Microsoft hosts and scales the models
- **No subscription quota required**: Billing is separate from your compute quotas
- **Pay-as-you-go pricing**: Only pay for tokens consumed
- **Immediate availability**: Create an endpoint and start using it right away
- **Enterprise security**: Same compliance and security guarantees as deployed models

Available models include OpenAI (GPT-4o, GPT-5), Mistral, DeepSeek, Cohere, and many others from the Azure AI model catalog.

## Proposed Approach

### Option A: User Creates Serverless Endpoint in Portal (Recommended)

Users would create a serverless API deployment through the Azure AI Foundry portal before running samples:

1. Sign in to ai.azure.com
2. Navigate to Model Catalog
3. Select GPT-4o (or preferred model) and click "Use this model"
4. Complete the deployment wizard (takes about one minute)
5. Copy the endpoint URL and API key
6. Add credentials to the samples `.env` file

This approach:
- Avoids all Bicep/infrastructure deployment
- Gives users control over which model and pricing tier to use
- Works with existing Azure subscriptions without special permissions
- Requires only a browser and Azure account

### Option B: Minimal Project with Serverless Deployment

Create a simplified infrastructure template that only provisions:

1. A Microsoft Foundry project (required for serverless endpoints)
2. A serverless API deployment for the chat model

This would still use `azd` but deploy far fewer resources - no storage accounts, no dedicated AI Services, no Log Analytics or Application Insights. The provisioning would be much faster and cheaper.

### Option C: Direct Azure OpenAI API Access

For users who already have an Azure OpenAI resource, support direct API access:

1. User provides their existing Azure OpenAI endpoint and key
2. Samples use the endpoint directly without needing Foundry project
3. Works with any OpenAI-compatible endpoint (including local LLMs)

## Required Changes

### Environment Variables

Add new serverless-specific variables:

```
AZURE_SERVERLESS_ENDPOINT     # Serverless API endpoint URL
AZURE_SERVERLESS_API_KEY      # API key for authentication
AZURE_SERVERLESS_MODEL        # Model name (e.g., gpt-4o)
```

### Configuration Priority

The samples would check for configuration in this order:

1. Serverless endpoint credentials (new, fastest to set up)
2. Foundry project endpoint (current approach, requires `azd up`)
3. Direct Azure OpenAI endpoint (legacy fallback)

If serverless credentials are present, skip Foundry project entirely.

### Embedding Model Consideration

The samples also need an embedding model for vector search. Options:

1. **Serverless embedding endpoint**: User creates a second serverless deployment for embeddings
2. **Azure OpenAI embeddings**: Use existing Azure OpenAI endpoint for embeddings
3. **Local embeddings**: Use a lightweight local model like sentence-transformers

For the simplest setup, recommend Option 1 - user creates both a chat model and embedding model serverless endpoint. This keeps everything consistent and pay-as-you-go.

## Updated Setup Flow

### Before (Current)

```
1. Install UV and Azure CLI          (5 minutes)
2. Run azd up                        (10-15 minutes)
3. Wait for provisioning             (5-10 minutes)
4. Run setup_env.py                  (1 minute)
5. Configure Neo4j credentials       (2 minutes)
6. Run samples                       (immediate)

Total: ~25-30 minutes
```

### After (With Serverless)

```
1. Install UV                        (2 minutes)
2. Create serverless endpoints       (5 minutes, via portal)
3. Copy endpoint URLs and keys       (1 minute)
4. Configure Neo4j credentials       (2 minutes)
5. Run samples                       (immediate)

Total: ~10 minutes
```

## Cost Comparison

### Current (Deployed Infrastructure)

- Azure AI Services: Fixed cost per hour/month even when idle
- Storage Account: Small but ongoing cost
- Log Analytics: Ingestion costs
- Application Insights: Retention costs

Total: Approximately $50-100/month even with minimal usage

### Serverless

- Chat model: ~$0.01-0.03 per 1K tokens (varies by model)
- Embedding model: ~$0.0001 per 1K tokens
- No idle costs

Running all 8 demos end-to-end: approximately $0.05-0.20 total

## Documentation Updates

If this approach is adopted, documentation should include:

1. A "Quick Start with Serverless" section in SETUP.md
2. Step-by-step screenshots for creating serverless endpoints
3. Explanation of when to use serverless vs. deployed infrastructure
4. Cost estimation for running demos

## Limitations

Serverless models have some constraints to be aware of:

- **Rate limits**: 200K tokens/minute, 1K requests/minute (sufficient for demos)
- **Regional availability**: Not all models available in all regions
- **Model versions**: Always uses latest version (no pinning to specific version)
- **No fine-tuning**: Cannot use fine-tuned models with serverless

For demo and learning purposes, none of these limitations are significant.

## Recommendation

Implement Option A (user creates serverless endpoint in portal) as the primary quick-start path, while keeping the current `azd up` approach available for users who want the full Foundry project experience.

This gives users the fastest path to running demos while preserving flexibility for more advanced scenarios.

## Sources

- [Deploy models as serverless API deployments - Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/deploy-models-serverless)
- [Foundry Models Overview - Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/foundry-models-overview)
- [Serverless API inference examples - Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/models-inference-examples)
