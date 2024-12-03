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


def get_latest_version(package_name, repository_url):
    """
    Получает последнюю доступную версию пакета из регистрационного API.
    """
    registration_index_url = get_registration_index_url(repository_url, package_name)
    response = requests.get(registration_index_url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch registration index for package {package_name}: {response.status_code}")

    data = response.json()

    # Получение последней версии из данных регистрационного индекса
    # Обычно последние элементы в 'items' содержат последние версии
    # Здесь предполагаем, что данные упорядочены по версиям
    # Можно также использовать семантическую сортировку версий
    pages = data.get('items', [])
    if not pages:
        raise Exception(f"No registration pages found for package {package_name}")

    # Предполагаем, что последняя страница содержит последние версии
    last_page = pages[-1]
    if isinstance(last_page, str):
        # Иногда страницы могут быть представлены как строки (URL)
        last_page = requests.get(last_page).json()

    items = last_page.get('items', [])
    if not items:
        raise Exception(f"No items found in the last registration page for package {package_name}")

    # Предполагаем, что последняя запись содержит последнюю версию
    latest_entry = items[-1]
    latest_version = latest_entry['catalogEntry']['version']
    return latest_version


def get_download_url(package_name, version, repository_url):
    """
    Получает URL для скачивания .nupkg файла указанного пакета и версии.
    """
    package_lower = package_name.lower()
    registration_version_url = f"{repository_url}/registration5-gz-semver2/{package_lower}/{version}.json"
    response = requests.get(registration_version_url)
    if response.status_code != 200:
        raise Exception(
            f"Failed to fetch registration data for package {package_name} version {version}: {response.status_code}")

    data = response.json()

    # Извлекаем URL для скачивания .nupkg файла
    # В зависимости от структуры API, путь может отличаться
    # Проверяем наличие 'catalogEntry' и 'packageContent'
    catalog_entry = data.get('catalogEntry', {})
    download_url = catalog_entry.get('packageContent')
    if not download_url:
        raise Exception(f"No download URL found for package {package_name} version {version}")

    return download_url


def download_nupkg(package_name, version, repository_url):
    """
    Скачивает nupkg файл для данного пакета и версии из репозитория.
    """
    download_url = get_download_url(package_name, version, repository_url)
    response = requests.get(download_url)
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
        # Получаем последнюю версию пакета
        version = get_latest_version(package_name, repository_url)
        print(f"Processing {package_name} version {version}")

        # Скачиваем nupkg файл
        nupkg_stream = download_nupkg(package_name, version, repository_url)

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
