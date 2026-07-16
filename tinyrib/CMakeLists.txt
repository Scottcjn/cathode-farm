cmake_minimum_required(VERSION 3.10)
project(tinyrib C)
add_application(TinyRIB tinyrib.c)
target_link_libraries(TinyRIB m)
