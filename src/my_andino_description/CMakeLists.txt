cmake_minimum_required(VERSION 3.8)
project(my_andino_description)

# خيارات التحذير عند استخدام GCC أو Clang
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# العثور على تبعية ament_cmake
find_package(ament_cmake REQUIRED)

# إذا كان لديك تبعيات إضافية (مثل urdf أو xacro) أضفها هنا:
# find_package(urdf REQUIRED)
# find_package(xacro REQUIRED)

# تثبيت مجلدات urdf و meshes داخل مسار التثبيت النهائي
install(
  DIRECTORY urdf meshes
  DESTINATION share/${PROJECT_NAME}
)

# إعدادات الاختبارات والتحقق (اختياري)
if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

# تعريف الحزمة لـ ament
ament_package()
