# Визуализатор зависимостей Git-репозитория

## Общее описание

Этот проект реализует инструмент командной строки для построения и визуализации графа зависимостей .NET-пакетов (nupkg) с использованием представления Graphviz. Визуализатор анализирует зависимости между пакетами, включая транзитивные зависимости, и выводит результат в виде кода Graphviz. Инструмент позволяет пользователю исследовать структуру зависимостей .NET-пакетов с помощью различных параметров командной строки.

---

## Функции и настройки

### Основные функции

- **Построение графа зависимостей .NET-пакетов:**
  - Визуализация зависимостей между пакетами в формате Graphviz.
  - Включение транзитивных зависимостей.
- **Поддержка гибкой настройки:**
  - Указание пути к программе для визуализации графов.
  - Задание максимальной глубины анализа зависимостей.
  - Указание URL-адреса репозитория для получения информации о пакетах.
- **Гибкая настройка ввода и вывода:**
  - Входные параметры включают имя пакета, путь к файлу с результатами, URL-адрес репозитория.
  - Вывод на экран в виде кода Graphviz.

### Параметры командной строки

- `--graphviz_path`: Путь к программе Graphviz (`dot`) для генерации изображений.
- `--package_name`: Имя анализируемого .NET-пакета.
- `--output_path`: Путь к файлу для сохранения результата в формате `.dot`.
- `--max_depth`: Максимальная глубина анализа зависимостей (по умолчанию 3).
- `--repository_url`: URL-адрес репозитория для получения информации о зависимостях.

### Реализация функций
1. **Получение всех версий пакета из NuGet API:** 
    ```python
    def get_all_versions_flatcontainer(package_name):
    flatcontainer_index_url = f"https://api.nuget.org/v3-flatcontainer/{package_name.lower()}/index.json"
    response = requests.get(flatcontainer_index_url)
    data = response.json()
    versions = data.get('versions', [])
    return versions

2. **Выбор последней стабильной версии:** 
    ```python
    def get_latest_stable_version(versions):
    stable_versions = [v for v in versions if not any(pre in v.lower() for pre in ['-beta', '-rc', '-preview', '-dev'])]
    latest_version = max(stable_versions, key=version.parse)
    return latest_version
    
3. **Скачивание `.nupkg` файла пакета:**
    ```python
    def download_nupkg(package_name, version):
    download_url = f"https://api.nuget.org/v3-flatcontainer/{package_name}/{version}/{package_name}.{version}.nupkg"
    response = requests.get(download_url)
    return io.BytesIO(response.content)
  
4. **Извлечение зависимостей из `.nuspec` файла:**
    ```python
    def extract_dependencies(nupkg_stream):
    with zipfile.ZipFile(nupkg_stream) as z:
    nuspec_files = [f for f in z.namelist() if f.endswith('.nuspec')]
    nuspec_content = z.read(nuspec_files[0])
    root = ET.fromstring(nuspec_content)
    dependencies = [dep.attrib.get('id') for dep in root.findall('.//dependency')]
    return dependencies

5. **Построение графа зависимостей:**
    ```python
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
    versions = get_all_versions_flatcontainer(package_name)
    latest_version = get_latest_stable_version(versions)
    nupkg_stream = download_nupkg(package_name, latest_version)
    dependencies = extract_dependencies(nupkg_stream)
    graph[package_name] = dependencies

    for dep in dependencies:
        build_dependency_graph(dep, repository_url, max_depth, current_depth + 1, graph, visited)
    except Exception as e:
    print(f"Error processing package {package_name}: {e}")

    return graph

6. **Генерация кода в формате Graphviz:**
    ```python
    def generate_dot(graph):
    dot = "digraph Dependencies {\n"
    for pkg, deps in graph.items():
    for dep in deps:
        dot += f'    "{pkg}" -> "{dep}";\n'
    dot += "}"
    return dot

7. **Основная функция main:**
    ```python
    def main():
    args = parse_arguments()
    graph = build_dependency_graph(args.package_name, args.repository_url, args.max_depth)
    dot_code = generate_dot(graph)
    with open(args.output_path, 'w', encoding='utf-8') as f:
    f.write(dot_code)
    print(dot_code)

  
## Команды для сборки проекта

1. **Установка зависимостей:**
   Для работы проекта требуется Python версии 3.7 или выше и библиотеки:
   ```bash
   pip install requests packaging
   
2. **Запуск визуализатора:**
   Для проверки корректности функций выполните:
   ```bash
   python dependency_visualizer.py --visualizer_path "C:\\Program Files\\Graphviz\\bin\\dot.exe" --package_name "Newtonsoft.Json" --output_path "output/dependencies.dot" --max_depth 3 --repository_url "https://api.nuget.org/v3"

3. **Запуск тестов:**
   Для проверки корректности функций выполните:
   ```bash
   python -m unittest discover -s tests


---
 
## Примеры использования

Запуск визуализатора:

    
    python dependency_visualizer.py --visualizer_path "C:\\Program Files\\Graphviz\\bin\\dot.exe" --package_name "Newtonsoft.Json" --output_path "output/dependencies.dot" --max_depth 3 --repository_url "https://api.nuget.org/v3"

    python dependency_visualizer.py --visualizer_path "C:\\Program Files\\Graphviz\\bin\\dot.exe" --package_name "NUnit" --output_path "output/dependencies.dot" --max_depth 1 --repository_url "https://api.nuget.org/v3"

    
 **Пример сеанса работы:**

 С помощью ручного ввода рассмотрим как работает визуализатор
 
   
![image](https://github.com/user-attachments/assets/26d144bb-37b4-4bc1-93dc-49446a779e04)


---

## Результаты прогонов тестов

**Тестовый файл для проверки всех функций**
````
# tests/test_dependency_visualizer.py

import unittest
from unittest.mock import patch, Mock
from io import BytesIO
import zipfile  # Добавлен импорт для zipfile
from dependency_visualizer import (
    get_latest_stable_version,
    extract_dependencies,
    build_dependency_graph,
    generate_dot
)
from packaging import version


class TestDependencyVisualizer(unittest.TestCase):

    def test_get_latest_stable_version(self):
        versions = [
            '1.0.0',
            '1.1.0-beta',
            '1.2.0',
            '2.0.0-rc1',
            '2.1.0',
            '3.0.0-dev',
            '3.1.0'
        ]
        expected = '3.1.0'
        result = get_latest_stable_version(versions)
        self.assertEqual(result, expected)

    def test_get_latest_stable_version_no_stable(self):
        versions = [
            '1.0.0-beta',
            '1.1.0-rc',
            '2.0.0-dev'
        ]
        with self.assertRaises(Exception) as context:
            get_latest_stable_version(versions)
        self.assertIn("No stable versions found", str(context.exception))

    def test_extract_dependencies(self):
        # Создаем пример .nuspec файла
        nuspec_content = '''<?xml version="1.0"?>
        <package>
          <metadata>
            <dependencies>
              <dependency id="Newtonsoft.Json" version="12.0.3" />
              <dependency id="Serilog" version="2.10.0" />
            </dependencies>
          </metadata>
        </package>'''

        # Создаем mock nupkg как ZIP с .nuspec
        mock_nupkg = BytesIO()
        with zipfile.ZipFile(mock_nupkg, 'w') as z:
            z.writestr('package.nuspec', nuspec_content)
        mock_nupkg.seek(0)

        dependencies = extract_dependencies(mock_nupkg)
        expected = ['Newtonsoft.Json', 'Serilog']
        self.assertEqual(set(dependencies), set(expected))


    @patch('dependency_visualizer.get_all_versions_flatcontainer')
    @patch('dependency_visualizer.download_nupkg')
    @patch('dependency_visualizer.extract_dependencies')
    def test_build_dependency_graph(self, mock_extract, mock_download, mock_get_versions):
        # Настраиваем моки
        mock_get_versions.return_value = ['1.0.0', '1.1.0', '2.0.0']
        mock_download.return_value = BytesIO(b"fake nupkg content")
        mock_extract.return_value = ['DepA', 'DepB']

        # Допустим, DepA имеет свои зависимости
        def side_effect_extract(nupkg_stream):
            if mock_download.call_count == 1:
                return ['DepA', 'DepB']
            elif mock_download.call_count == 2:
                return ['DepC']
            return []

        mock_extract.side_effect = side_effect_extract

        graph = build_dependency_graph(
            package_name='TestPackage',
            repository_url='https://api.nuget.org/v3',
            max_depth=2
        )

        expected_graph = {
            'TestPackage': ['DepA', 'DepB'],
            'DepA': ['DepC'],
            'DepB': [],
            'DepC': [],  # Добавляем DepC, который в реальности есть
        }

        self.assertEqual(graph, expected_graph)

    def test_generate_dot(self):
        graph = {
            'PackageA': ['PackageB', 'PackageC'],
            'PackageB': ['PackageD'],
            'PackageC': [],
            'PackageD': []
        }
        expected_dot = """digraph Dependencies {
    "PackageA" -> "PackageB";
    "PackageA" -> "PackageC";
    "PackageB" -> "PackageD";
    "PackageC" -> "";
    "PackageD" -> "";
}"""
        # Однако, в вашем скрипте PackageC и PackageD не имеют зависимостей, поэтому они не должны иметь стрелок.
        expected_dot = """digraph Dependencies {
    "PackageA" -> "PackageB";
    "PackageA" -> "PackageC";
    "PackageB" -> "PackageD";
}"""
        result_dot = generate_dot(graph)
        self.assertEqual(result_dot.strip(), expected_dot.strip())


if __name__ == '__main__':
    unittest.main()


````
Запуск тестов с помощью `:
````
python -m unittest discover -s tests

````

**Вывод**:

![image](https://github.com/user-attachments/assets/7ea22543-a217-4711-abf5-33712ffc977e)


Все тесты успешно пройдены, что подтверждает корректность работы всех функций визуализатора.
