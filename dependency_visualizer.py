import argparse
import os
import requests
import zipfile
import io
import xml.etree.ElementTree as ET
from packaging import version  # Для работы с версиями


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
        help="URL to the NuGet repository (e.g., https://api.nuget.org/v3)"
    )
    return parser.parse_args()


def get_flatcontainer_index_url(package_name):
    """
    Получает URL для Flat Container API для указанного пакета.
    """
    package_lower = package_name.lower()
    flatcontainer_index_url = f"https://api.nuget.org/v3-flatcontainer/{package_lower}/index.json"
    return flatcontainer_index_url


def get_all_versions_flatcontainer(package_name):
    """
    Получает все доступные версии пакета из Flat Container API.
    """
    flatcontainer_index_url = get_flatcontainer_index_url(package_name)
    print(f"Fetching Flat Container index URL: {flatcontainer_index_url}")  # Отладка

    response = requests.get(flatcontainer_index_url)
    print(f"Response status code: {response.status_code}")  # Отладка

    if response.status_code != 200:
        raise Exception(f"Failed to fetch versions for package {package_name}: {response.status_code}")

    try:
        data = response.json()
        print(f"Flat Container index data: {data}")  # Отладка
    except ValueError as e:
        print(f"Error parsing JSON: {e}")  # Отладка
        raise Exception(f"Invalid JSON response for package {package_name}")

    versions = data.get('versions', [])
    print(f"All available versions (flatcontainer): {versions}")  # Отладка

    if not versions:
        raise Exception(f"No versions found for package {package_name}")

    return versions


def get_latest_stable_version(versions):
    """
    Выбирает последнюю стабильную версию из списка версий.
    Фильтрует предрелизные версии на основе наличия ключевых слов и свойства is_prerelease.
    """
    stable_versions = []
    for v in versions:
        # Исключаем предрелизные версии по ключевым словам
        if any(pre in v.lower() for pre in ['-beta', '-rc', '-preview', '-dev']):
            print(f"Skipping pre-release version (keyword): {v}")  # Отладка
            continue
        try:
            parsed_version = version.parse(v)
            if parsed_version.is_prerelease:
                print(f"Skipping pre-release version (is_prerelease): {v}")  # Отладка
                continue
            stable_versions.append(parsed_version)
            print(f"Added stable version: {v}")  # Отладка
        except Exception as e:
            print(f"Skipping version '{v}' due to parsing error: {e}")  # Отладка

    if not stable_versions:
        raise Exception("No stable versions found.")

    latest_version = max(stable_versions)
    latest_version_str = str(latest_version)
    print(f"Latest stable version: {latest_version_str}")  # Отладка
    return latest_version_str


def get_download_url(package_name, version):
    """
    Получает URL для скачивания .nupkg файла через Flat Container API.
    """
    package_lower = package_name.lower()
    flatcontainer_download_url = f"https://api.nuget.org/v3-flatcontainer/{package_lower}/{version}/{package_lower}.{version}.nupkg"
    print(f"Fetching Flat Container download URL: {flatcontainer_download_url}")  # Отладка
    return flatcontainer_download_url


def download_nupkg(package_name, version):
    """
    Скачивает nupkg файл для данного пакета и версии через Flat Container API.
    """
    download_url = get_download_url(package_name, version)
    print(f"Downloading nupkg from URL: {download_url}")  # Отладка
    response = requests.get(download_url)
    print(f"Download response status code: {response.status_code}")  # Отладка

    if response.status_code == 200:
        return io.BytesIO(response.content)
    else:
        raise FileNotFoundError(f"Package {package_name} version {version} not found at {download_url}")


def extract_dependencies(nupkg_stream):
    """
    Извлекает зависимости из .nuspec файла внутри nupkg потока.
    """
    with zipfile.ZipFile(nupkg_stream) as z:
        # Найти .nuspec файл
        nuspec_files = [f for f in z.namelist() if f.endswith('.nuspec')]
        if not nuspec_files:
            raise FileNotFoundError(".nuspec file not found in the nupkg")
        nuspec_content = z.read(nuspec_files[0])

    # Парсинг XML с учетом пространств имен
    root = ET.fromstring(nuspec_content)

    # Извлечь пространство имен из корневого элемента
    namespace = ''
    if root.tag.startswith('{'):
        namespace = root.tag.split('}')[0].strip('{')

    ns = {'ns': namespace} if namespace else {}

    dependencies = set()  # Используем set для избежания дублирования
    metadata = root.find('ns:metadata', ns) if namespace else root.find('metadata')
    if metadata is None:
        raise ValueError("Invalid .nuspec format: missing metadata")

    dependencies_node = metadata.find('ns:dependencies', ns) if namespace else metadata.find('dependencies')
    if dependencies_node is not None:
        # Обработка групп зависимостей (например, по целевым фреймворкам)
        groups = dependencies_node.findall('ns:group', ns) if namespace else dependencies_node.findall('group')
        for group in groups:
            deps = group.findall('ns:dependency', ns) if namespace else group.findall('dependency')
            for dep in deps:
                dep_id = dep.attrib.get('id')
                if dep_id:
                    dependencies.add(dep_id)
                    print(f"Found dependency: {dep_id}")  # Отладка
        # Обработка зависимостей без группировки
        deps = dependencies_node.findall('ns:dependency', ns) if namespace else dependencies_node.findall('dependency')
        for dep in deps:
            dep_id = dep.attrib.get('id')
            if dep_id:
                dependencies.add(dep_id)
                print(f"Found dependency: {dep_id}")  # Отладка

    return list(dependencies)


def build_dependency_graph(package_name, repository_url, max_depth, current_depth=0, graph=None, visited=None):
    if graph is None:
        graph = {}
    if visited is None:
        visited = set()

    if current_depth > max_depth:
        return graph
    if package_name.lower() in visited:
        return graph

    visited.add(package_name.lower())

    try:
        # Получаем все доступные версии пакета
        versions = get_all_versions_flatcontainer(package_name)
        # Выбираем последнюю стабильную версию
        latest_version = get_latest_stable_version(versions)
        print(f"Processing {package_name} version {latest_version}")

        # Скачиваем nupkg файл
        nupkg_stream = download_nupkg(package_name, latest_version)

        # Извлекаем зависимости
        dependencies = extract_dependencies(nupkg_stream)
        graph[package_name] = dependencies

        # Рекурсивно обрабатываем зависимости
        for dep in dependencies:
            build_dependency_graph(dep, repository_url, max_depth, current_depth + 1, graph, visited)
    except Exception as e:
        print(f"Error processing package {package_name}: {e}")

    return graph


def generate_dot(graph):
    """
    Генерирует Graphviz DOT код из графа зависимостей.
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

    # Создаем папку, если она не существует
    output_dir = os.path.dirname(args.output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Запись DOT кода в указанный файл
    with open(args.output_path, 'w', encoding='utf-8') as f:
        f.write(dot_code)

    # Вывод DOT кода на экран
    print(dot_code)

    # Опционально: вызов Graphviz для генерации изображения
    # import subprocess
    # subprocess.run([args.visualizer_path, '-Tpng', args.output_path, '-o', 'output/dependencies.png'])


if __name__ == "__main__":
    main()
