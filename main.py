import argparse
import os
import requests
import zipfile
import io
import xml.etree.ElementTree as ET
from packaging import version


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


def get_registration_index_url(repository_url, package_name):
    """
    Получает URL регистрационного индекса для указанного пакета.
    """
    # Преобразуем имя пакета в нижний регистр, так как NuGet API чувствителен к регистру
    package_lower = package_name.lower()
    registration_index_url = f"{repository_url}/registration5-gz-semver2/{package_lower}/index.json"
    return registration_index_url


def get_all_versions(package_name, repository_url):
    """
    Получает все доступные версии пакета из регистрационного API.
    """
    registration_index_url = get_registration_index_url(repository_url, package_name)
    print(f"Fetching registration index URL: {registration_index_url}")  # Отладка

    response = requests.get(registration_index_url)
    print(f"Response status code: {response.status_code}")  # Отладка

    if response.status_code != 200:
        raise Exception(f"Failed to fetch registration index for package {package_name}: {response.status_code}")

    try:
        data = response.json()
        print(f"Registration index data: {data}")  # Отладка
    except ValueError as e:
        print(f"Error parsing JSON: {e}")  # Отладка
        raise Exception(f"Invalid JSON response for package {package_name}")

    # Получение всех версий из данных регистрационного индекса
    pages = data.get('items', [])
    print(f"Registration pages: {pages}")  # Отладка

    if not pages:
        raise Exception(f"No registration pages found for package {package_name}")

    versions = []

    for page in pages:
        if isinstance(page, str):
            # Если страницы представлены как строки (URL), получаем JSON
            page_response = requests.get(page)
            print(f"Fetching registration page URL: {page}")  # Отладка
            if page_response.status_code != 200:
                print(f"Failed to fetch registration page: {page_response.status_code}")  # Отладка
                continue
            page_data = page_response.json()
        else:
            page_data = page

        inner_items = page_data.get('items', [])
        print(f"Inner registration items: {inner_items}")  # Отладка

        for entry in inner_items:
            catalog_entry = entry.get('catalogEntry', {})
            pkg_version = catalog_entry.get('version')
            if pkg_version:
                versions.append(pkg_version)

    if not versions:
        raise Exception(f"No versions found for package {package_name}")

    print(f"All available versions: {versions}")  # Отладка
    return versions


def get_latest_stable_version(versions):
    """
    Выбирает последнюю стабильную версию из списка версий.
    """
    stable_versions = [v for v in versions if not version.parse(v).is_prerelease]
    if not stable_versions:
        raise Exception("No stable versions found.")

    latest_version = max(stable_versions, key=version.parse)
    print(f"Latest stable version: {latest_version}")  # Отладка
    return latest_version


def get_download_url(package_name, version, repository_url):
    """
    Получает URL для скачивания .nupkg файла указанного пакета и версии.
    """
    package_lower = package_name.lower()
    registration_version_url = f"{repository_url}/registration5-gz-semver2/{package_lower}/{version}.json"
    print(f"Fetching registration version URL: {registration_version_url}")  # Отладка

    response = requests.get(registration_version_url)
    print(f"Response status code: {response.status_code}")  # Отладка

    if response.status_code != 200:
        raise Exception(f"Failed to fetch registration data for package {package_name} version {version}: {response.status_code}")

    try:
        data = response.json()
        print(f"Registration data: {data}")  # Отладка
    except ValueError as e:
        print(f"Error parsing JSON: {e}")  # Отладка
        raise Exception(f"Invalid JSON response for package {package_name} version {version}")

    items = data.get('items', [])
    print(f"Items: {items}")  # Отладка

    if not items:
        raise Exception(f"No items found in registration data for package {package_name} version {version}")

    last_page = items[-1]
    print(f"Last page: {last_page}")  # Отладка

    if isinstance(last_page, dict) and 'items' in last_page:
        inner_items = last_page['items']
        print(f"Inner items: {inner_items}")  # Отладка

        if not inner_items:
            raise Exception(f"No inner items found in the last registration page for package {package_name} version {version}")

        catalog_entry = inner_items[0].get('catalogEntry', {})
        print(f"Catalog Entry: {catalog_entry}")  # Отладка
    else:
        raise Exception(f"'catalogEntry' not found in registration data for package {package_name} version {version}")

    download_url = catalog_entry.get('packageContent')
    print(f"Download URL: {download_url}")  # Отладка

    if not download_url:
        raise Exception(f"No download URL found for package {package_name} version {version}")

    return download_url


def download_nupkg(package_name, version, repository_url):
    """
    Скачивает nupkg файл для данного пакета и версии из репозитория.
    """
    download_url = get_download_url(package_name, version, repository_url)
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

    # Парсинг XML
    root = ET.fromstring(nuspec_content)

    dependencies = []
    metadata = root.find('metadata')
    if metadata is None:
        raise ValueError("Invalid .nuspec format: missing metadata")

    dependencies_node = metadata.find('dependencies')
    if dependencies_node is not None:
        # Обработка групп зависимостей (например, по целевым фреймворкам)
        for group in dependencies_node.findall('group'):
            for dep in group.findall('dependency'):
                dependencies.append(dep.attrib['id'])
        # Обработка зависимостей без группировки
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
    if package_name.lower() in visited:
        return graph

    visited.add(package_name.lower())

    try:
        # Получаем все доступные версии пакета
        versions = get_all_versions(package_name, repository_url)
        # Выбираем последнюю стабильную версию
        latest_version = get_latest_stable_version(versions)
        print(f"Processing {package_name} version {latest_version}")

        # Скачиваем nupkg файл
        nupkg_stream = download_nupkg(package_name, latest_version, repository_url)

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
