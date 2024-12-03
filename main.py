import argparse
import os
import requests
import zipfile
import io
import xml.etree.ElementTree as ET


def parse_arguments():
    parser = argparse.ArgumentParser(description="Visualize .NET package dependencies")
    parser.add_argument(
        "--visualizer_path",
        type=str,
        required=True,
        help="Path to the Graphviz 'dot' executable"
    )
    parser.add_argument(
        "--package_name",
        type=str,
        required=True,
        help="Name of the package to analyze"
    )
    parser.add_argument(
        "--output_path",
        type=str,
        required=True,
        help="Path to the output DOT file"
    )
    parser.add_argument(
        "--max_depth",
        type=int,
        default=3,
        help="Maximum depth for dependency analysis"
    )
    parser.add_argument(
        "--repository_url",
        type=str,
        required=True,
        help="URL to the NuGet repository"
    )
    return parser.parse_args()


def download_nupkg(package_name, repository_url):
    """
    Downloads the nupkg file for the given package from the repository URL.
    """
    # Простой пример: предполагаем, что URL имеет формат repository_url/package_name/version/package_name.version.nupkg
    # Для реального случая может понадобиться дополнительная логика для поиска последней версии
    # Здесь используем пример фиксированной версии
    version = "1.0.0"  # В реальном случае нужно определить версию
    nupkg_url = f"{repository_url}/{package_name}/{version}/{package_name}.{version}.nupkg"

    response = requests.get(nupkg_url)
    if response.status_code == 200:
        return io.BytesIO(response.content)
    else:
        raise FileNotFoundError(f"Package {package_name} not found at {nupkg_url}")


def extract_dependencies(nupkg_stream):
    """
    Extracts dependencies from the .nuspec file within the nupkg stream.
    """
    with zipfile.ZipFile(nupkg_stream) as z:
        # Найти .nuspec файл
        nuspec_files = [f for f in z.namelist() if f.endswith('.nuspec')]
        if not nuspec_files:
            raise FileNotFoundError(".nuspec file not found in the nupkg")
        nuspec_content = z.read(nuspec_files[0])

    # Парсинг XML
    root = ET.fromstring(nuspec_content)

    dependencies = []
    metadata = root.find('metadata')
    if metadata is None:
        raise ValueError("Invalid .nuspec format: missing metadata")

    dependencies_node = metadata.find('dependencies')
    if dependencies_node is not None:
        for group in dependencies_node.findall('group'):
            for dep in group.findall('dependency'):
                dependencies.append(dep.attrib['id'])
        # Если зависимости не сгруппированы
        for dep in dependencies_node.findall('dependency'):
            dependencies.append(dep.attrib['id'])

    return dependencies


def build_dependency_graph(package_name, repository_url, max_depth, current_depth=0, graph=None, visited=None):
    if graph is None:
        graph = {}
    if visited is None:
        visited = set()

    if current_depth > max_depth:
        return graph
    if package_name in visited:
        return graph

    visited.add(package_name)

    try:
        nupkg_stream = download_nupkg(package_name, repository_url)
        dependencies = extract_dependencies(nupkg_stream)
        graph[package_name] = dependencies
        for dep in dependencies:
            build_dependency_graph(dep, repository_url, max_depth, current_depth + 1, graph, visited)
    except Exception as e:
        print(f"Error processing package {package_name}: {e}")

    return graph


def generate_dot(graph):
    """
    Generates Graphviz DOT code from the dependency graph.
    """
    dot = "digraph Dependencies {\n"
    for pkg, deps in graph.items():
        for dep in deps:
            dot += f'    "{pkg}" -> "{dep}";\n'
    dot += "}"
    return dot


def main():
    args = parse_arguments()

    graph = build_dependency_graph(
        package_name=args.package_name,
        repository_url=args.repository_url,
        max_depth=args.max_depth
    )

    dot_code = generate_dot(graph)

    # Запись в файл
    with open(args.output_path, 'w', encoding='utf-8') as f:
        f.write(dot_code)

    # Вывод на экран
    print(dot_code)

    # Опционально: вызов Graphviz для генерации изображения
    # import subprocess
    # subprocess.run([args.visualizer_path, '-Tpng', args.output_path, '-o', 'output.png'])


if __name__ == "__main__":
    main()
