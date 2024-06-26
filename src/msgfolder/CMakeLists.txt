cmake_minimum_required(VERSION 3.8)
project(msgfolder)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "clang")
    add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(std_msgs REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
    "msg/MachineCommand.msg"
    "msg/MachineStatus.msg"
    "msg/WateringCommand.msg"
    "msg/WateringStatus.msg"
    DEPENDENCIES builtin_interfaces std_msgs
)
install(
    FILES my_bridge_mapping.yaml
    DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
    find_package(ament_lint_auto REQUIRED)
    ament_lint_auto_find_test_dependencies()
endif()

ament_package()
