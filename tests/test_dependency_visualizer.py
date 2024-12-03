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


if __name__ == 'main':
    unittest.main()