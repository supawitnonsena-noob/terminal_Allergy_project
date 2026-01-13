// generated from rosidl_typesupport_fastrtps_c/resource/idl__rosidl_typesupport_fastrtps_c.h.em
// with input from lidarslam_msgs:msg/SubMap.idl
// generated code does not contain a copyright notice
#ifndef LIDARSLAM_MSGS__MSG__DETAIL__SUB_MAP__ROSIDL_TYPESUPPORT_FASTRTPS_C_H_
#define LIDARSLAM_MSGS__MSG__DETAIL__SUB_MAP__ROSIDL_TYPESUPPORT_FASTRTPS_C_H_


#include <stddef.h>
#include "rosidl_runtime_c/message_type_support_struct.h"
#include "rosidl_typesupport_interface/macros.h"
#include "lidarslam_msgs/msg/rosidl_typesupport_fastrtps_c__visibility_control.h"
#include "lidarslam_msgs/msg/detail/sub_map__struct.h"
#include "fastcdr/Cdr.h"

#ifdef __cplusplus
extern "C"
{
#endif

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_lidarslam_msgs
bool cdr_serialize_lidarslam_msgs__msg__SubMap(
  const lidarslam_msgs__msg__SubMap * ros_message,
  eprosima::fastcdr::Cdr & cdr);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_lidarslam_msgs
bool cdr_deserialize_lidarslam_msgs__msg__SubMap(
  eprosima::fastcdr::Cdr &,
  lidarslam_msgs__msg__SubMap * ros_message);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_lidarslam_msgs
size_t get_serialized_size_lidarslam_msgs__msg__SubMap(
  const void * untyped_ros_message,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_lidarslam_msgs
size_t max_serialized_size_lidarslam_msgs__msg__SubMap(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_lidarslam_msgs
bool cdr_serialize_key_lidarslam_msgs__msg__SubMap(
  const lidarslam_msgs__msg__SubMap * ros_message,
  eprosima::fastcdr::Cdr & cdr);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_lidarslam_msgs
size_t get_serialized_size_key_lidarslam_msgs__msg__SubMap(
  const void * untyped_ros_message,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_lidarslam_msgs
size_t max_serialized_size_key_lidarslam_msgs__msg__SubMap(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_lidarslam_msgs
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, lidarslam_msgs, msg, SubMap)();

#ifdef __cplusplus
}
#endif

#endif  // LIDARSLAM_MSGS__MSG__DETAIL__SUB_MAP__ROSIDL_TYPESUPPORT_FASTRTPS_C_H_
