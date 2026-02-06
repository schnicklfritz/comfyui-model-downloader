#!/bin/bash
# Master build script for Golemite
set -e

function build_clay() {
    echo "🪨 Building Golemite Clay (Alpine production image)..."
    docker build -f clay/Dockerfile.alpine -t golemite-clay:latest ./clay
    echo "✅ Clay image built: golemite-clay:latest"
}

function build_forge() {
    echo "🔥 Building Golemite Forge (Arch development image)..."
    docker build -f forge/Dockerfile.arch -t golemite-forge:latest ./forge
    echo "✅ Forge image built: golemite-forge:latest"
}

function build_formation() {
    local formation=$1
    echo "🔧 Building formation: $formation"
    # This builds a specialized image with the formation baked in
    docker build -f clay/Dockerfile.alpine \
        --build-arg FORMATION="$formation" \
        -t "golemite-${formation}:latest" \
        ./clay
    echo "✅ Formation image built: golemite-${formation}:latest"
}

function push_all() {
    local registry=$1
    echo "📤 Pushing images to registry: $registry"
    
    for image in golemite-clay golemite-forge; do
        docker tag "${image}:latest" "${registry}/${image}:latest"
        docker push "${registry}/${image}:latest"
        echo "  Pushed: ${registry}/${image}:latest"
    done
}

# Main execution
case "$1" in
    "clay")
        build_clay
        ;;
    "forge")
        build_forge
        ;;
    "formation")
        if [ -z "$2" ]; then
            echo "Usage: $0 formation <formation_name>"
            exit 1
        fi
        build_formation "$2"
        ;;
    "push")
        if [ -z "$2" ]; then
            echo "Usage: $0 push <registry_url>"
            exit 1
        fi
        push_all "$2"
        ;;
    "all")
        build_clay
        build_forge
        ;;
    *)
        echo "Golemite Build System"
        echo "Usage: $0 {clay|forge|formation|push|all}"
        echo ""
        echo "  clay        - Build production Alpine image"
        echo "  forge       - Build development Arch image"
        echo "  formation   - Build specialized formation image"
        echo "  push <reg>  - Push images to registry"
        echo "  all         - Build both clay and forge"
        exit 1
        ;;
esac
