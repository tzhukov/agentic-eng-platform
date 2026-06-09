# Tiltfile for Self-Correction Support Agent

# 1. Configuration
# Default values for local development
settings = {
    'namespace': 'agent-system',
    'chart_path': './deploy/charts/agent',
}

# 2. Namespace setup
local('kubectl create namespace %s --dry-run=client -o yaml | kubectl apply -f -' % settings['namespace'])

# 3. Agent Application Development
docker_build('agent-api-image', '.', dockerfile='Dockerfile')
docker_build('agent-web-image', '.', dockerfile='Dockerfile.web')

# 4. Helm Deployment
k8s_yaml(helm(
    settings['chart_path'],
    name='agent-stack',
    namespace=settings['namespace'],
    set=[
        'qdrant.config.telemetry_disabled=true',
    ]
))

# 5. Port Forwards
k8s_resource(
    'agent-stack-api',
    port_forwards=[
        '8000:8000', # FastAPI
    ],
)

k8s_resource(
    'agent-stack-web',
    port_forwards=[
        '8080:80',   # Web UI
    ],
)
# Also forward Qdrant/LangFuse if needed
k8s_resource('agent-stack-qdrant', port_forwards=['6333:6333'])
k8s_resource('agent-stack-langfuse-web', port_forwards=['3000:3000'])
