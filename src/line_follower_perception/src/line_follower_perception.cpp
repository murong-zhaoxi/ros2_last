// Copyright (c) 2024，D-Robotics.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include "line_follower_perception/line_follower_perception.h"

#include <cstring>
#include <cmath>
#include <sstream>
#include <string>
#include <opencv2/opencv.hpp>

#include "dnn_node/util/image_proc.h"
#include "hobot_cv/hobotcv_imgproc.h"

void prepare_nv12_tensor_without_padding(const char *image_data,
                                         int image_height,
                                         int image_width,
                                         hbDNNTensor *tensor) {
  auto &properties = tensor->properties;
  properties.tensorType = HB_DNN_IMG_TYPE_NV12;
  properties.tensorLayout = HB_DNN_LAYOUT_NCHW;
  auto &valid_shape = properties.validShape;
  valid_shape.numDimensions = 4;
  valid_shape.dimensionSize[0] = 1;
  valid_shape.dimensionSize[1] = 3;
  valid_shape.dimensionSize[2] = image_height;
  valid_shape.dimensionSize[3] = image_width;

  auto &aligned_shape = properties.alignedShape;
  aligned_shape = valid_shape;

  int32_t image_length = image_height * image_width * 3 / 2;

  hbSysAllocCachedMem(&tensor->sysMem[0], image_length);
  memcpy(tensor->sysMem[0].virAddr, image_data, image_length);

  hbSysFlushMem(&(tensor->sysMem[0]), HB_SYS_MEM_CACHE_CLEAN);
}

void prepare_nv12_tensor_without_padding(int image_height,
                                         int image_width,
                                         hbDNNTensor *tensor) {
  auto &properties = tensor->properties;
  properties.tensorType = HB_DNN_IMG_TYPE_NV12;
  properties.tensorLayout = HB_DNN_LAYOUT_NCHW;

  auto &valid_shape = properties.validShape;
  valid_shape.numDimensions = 4;
  valid_shape.dimensionSize[0] = 1;
  valid_shape.dimensionSize[1] = 3;
  valid_shape.dimensionSize[2] = image_height;
  valid_shape.dimensionSize[3] = image_width;

  auto &aligned_shape = properties.alignedShape;
  int32_t w_stride = ALIGN_16(image_width);
  aligned_shape.numDimensions = 4;
  aligned_shape.dimensionSize[0] = 1;
  aligned_shape.dimensionSize[1] = 3;
  aligned_shape.dimensionSize[2] = image_height;
  aligned_shape.dimensionSize[3] = w_stride;

  int32_t image_length = image_height * w_stride * 3 / 2;
  hbSysAllocCachedMem(&tensor->sysMem[0], image_length);
}

LineFollowerPerceptionNode::LineFollowerPerceptionNode(const std::string& node_name,
                      const NodeOptions& options)
  : DnnNode(node_name, options) {
  this->declare_parameter("model_path", "/userdata/resnet18/resnet18_224x224_nv12.bin");
  this->declare_parameter("model_name", "resnet18_224x224_nv12");
  if (GetParams() == false) {
    RCLCPP_ERROR(this->get_logger(), "LineFollowerPerceptionNode GetParams() failed\n\n");
    return;
  }
  
  if (Init() != 0) {
    RCLCPP_FATAL(this->get_logger(), "DNN model initialization failed");
    return;
  }

  publisher_ = this->create_publisher<geometry_msgs::msg::PointStamped>(  
            "line_track_center_detection", 10); 
  subscriber_ =
    this->create_subscription<hbm_img_msgs::msg::HbmMsg1080P>(
      "hbmem_img",
      rclcpp::SensorDataQoS(),
      std::bind(&LineFollowerPerceptionNode::subscription_callback,
      this,
      std::placeholders::_1)); 
  ready_ = true;
}

LineFollowerPerceptionNode::~LineFollowerPerceptionNode() {

}

bool LineFollowerPerceptionNode::GetParams() {
  model_path_ = this->get_parameter("model_path").as_string();
  model_name_ = this->get_parameter("model_name").as_string();
  if (model_path_.empty() || model_name_.empty()) {
    RCLCPP_ERROR(this->get_logger(), "model_path and model_name must not be empty");
    return false;
  }
  return true;
}

int LineFollowerPerceptionNode::SetNodePara() {
  if (!dnn_node_para_ptr_) {
    return -1;
  }
  RCLCPP_INFO(rclcpp::get_logger("LineFollowerPerceptionNode"), "path:%s\n", model_path_.c_str());
  RCLCPP_INFO(rclcpp::get_logger("LineFollowerPerceptionNode"), "name:%s\n", model_name_.c_str());
  dnn_node_para_ptr_->model_file = model_path_;
  dnn_node_para_ptr_->model_name = model_name_;
  dnn_node_para_ptr_->model_task_type = model_task_type_;
  dnn_node_para_ptr_->task_num = 4;
  return 0;
}

int LineFollowerPerceptionNode::PostProcess(
  const std::shared_ptr<DnnNodeOutput> &outputs) {
  if (!outputs || outputs->output_tensors.empty()) {
    RCLCPP_ERROR(this->get_logger(), "DNN returned no output tensors");
    return -1;
  }

  std::shared_ptr<LineCoordinateParser> line_coordinate_parser =
      std::make_shared<LineCoordinateParser>();

  std::shared_ptr<LineCoordinateResult> result =
      std::make_shared<LineCoordinateResult>();

  if (line_coordinate_parser->Parse(result, outputs->output_tensors[0]) != 0) {
    RCLCPP_ERROR(this->get_logger(), "Failed to parse DNN output");
    return -1;
  }

  auto point_msg = geometry_msgs::msg::PointStamped();
  
  point_msg.header.stamp = this->now();  
  point_msg.header.frame_id = "image_pixels";
  point_msg.point.x = result->x;
  point_msg.point.y = result->y;
  point_msg.point.z = 0;

  publisher_->publish(point_msg);  
  return 0;
}

void LineFollowerPerceptionNode::subscription_callback(
    const hbm_img_msgs::msg::HbmMsg1080P::SharedPtr msg) {
  int ret = 0;
  if (!msg || !rclcpp::ok()) {
    return;
  }
  if (msg->width < 1920 || msg->height < 948 ||
      msg->data.size() < static_cast<size_t>(msg->height) * msg->width * 3 / 2) {
    RCLCPP_ERROR_THROTTLE(
      this->get_logger(), *this->get_clock(), 5000,
      "Invalid NV12 image dimensions or data length");
    return;
  }
  std::stringstream ss;
  ss << "Recved img encoding: "
     << std::string(reinterpret_cast<const char*>(msg->encoding.data()))
     << ", h: " << msg->height << ", w: " << msg->width
     << ", step: " << msg->step << ", index: " << msg->index
     << ", stamp: " << msg->time_stamp.sec << "_"
     << msg->time_stamp.nanosec << ", data size: " << msg->data_size;
  RCLCPP_DEBUG(rclcpp::get_logger("LineFollowerPerceptionNode"), "%s", ss.str().c_str());

  auto model_manage = GetModel();
  if (!model_manage) {
    RCLCPP_ERROR(rclcpp::get_logger("LineFollowerPerceptionNode"), "Invalid model");
    return;
  }

  hbDNNRoi roi;
  roi.left = 0;
  roi.top = 500;
  roi.right = 1920;
  roi.bottom = 948;

  cv::Mat img_mat(msg->height * 3 / 2, msg->width, CV_8UC1, (void*)(msg->data.data()));
  cv::Range rowRange(roi.top, roi.bottom);
  cv::Range colRange(roi.left, roi.right);
  cv::Mat crop_img_mat = hobot_cv::hobotcv_crop(img_mat, msg->height, msg->width, 224, 224, rowRange, colRange);
  if (crop_img_mat.empty()) {
    RCLCPP_ERROR(this->get_logger(), "Failed to crop the NV12 image");
    return;
  }

  std::shared_ptr<hobot::dnn_node::NV12PyramidInput> pyramid = nullptr;
  pyramid = hobot::dnn_node::ImageProc::GetNV12PyramidFromNV12Img(
      reinterpret_cast<const char*>(crop_img_mat.data),
      224,
      224,
      224,
      224);
  if (!pyramid) {
    RCLCPP_ERROR(rclcpp::get_logger("LineFollowerPerceptionNode"), "Get Nv12 pym fail!");
    return;
  }
  std::vector<std::shared_ptr<DNNInput>> inputs;
  auto rois = std::make_shared<std::vector<hbDNNRoi>>();
  roi.left = 0;
  roi.top = 0;
  roi.right = 224;
  roi.bottom = 224;
  rois->push_back(roi);

  for (size_t i = 0; i < rois->size(); i++) {
    for (int32_t j = 0; j < model_manage->GetInputCount(); j++) {
      inputs.push_back(pyramid);
    }
  }

  auto dnn_output = std::shared_ptr<DnnNodeOutput>();

  ret = Predict(inputs, dnn_output, rois);
  if (ret != 0) {
    RCLCPP_ERROR(this->get_logger(), "DNN inference request failed: %d", ret);
  }
}

int LineFollowerPerceptionNode::Predict(
  std::vector<std::shared_ptr<DNNInput>> &dnn_inputs,
  const std::shared_ptr<DnnNodeOutput> &output,
  const std::shared_ptr<std::vector<hbDNNRoi>> rois) {
  RCLCPP_DEBUG(
    rclcpp::get_logger("LineFollowerPerceptionNode"),
    "input size:%zu roi size:%zu", dnn_inputs.size(), rois->size());
  return Run(dnn_inputs,
             output,
             rois,
             true);
}


int32_t LineCoordinateParser::Parse(
    std::shared_ptr<LineCoordinateResult> &output,
    std::shared_ptr<DNNTensor> &output_tensor) {
  if (!output_tensor || !output_tensor->sysMem[0].virAddr) {
    RCLCPP_ERROR(rclcpp::get_logger("LineFollowerPerceptionNode"), "invalid out tensor");
    return -1;
  }
  std::shared_ptr<LineCoordinateResult> result;
  if (!output) {
    result = std::make_shared<LineCoordinateResult>();
    output = result;
  } else {
    result = std::dynamic_pointer_cast<LineCoordinateResult>(output);
  }
  if (!result) {
    RCLCPP_ERROR(
      rclcpp::get_logger("LineFollowerPerceptionNode"),
      "invalid line-coordinate result type");
    return -1;
  }
  DNNTensor &tensor = *output_tensor;
  if (tensor.properties.validShape.numDimensions < 2 ||
      tensor.properties.validShape.dimensionSize[0] *
        tensor.properties.validShape.dimensionSize[1] < 2) {
    RCLCPP_ERROR(
      rclcpp::get_logger("LineFollowerPerceptionNode"),
      "Expected an output tensor with at least two values");
    return -1;
  }
  const int32_t *shape = tensor.properties.validShape.dimensionSize;
  RCLCPP_DEBUG(rclcpp::get_logger("LineFollowerPerceptionNode"),
               "PostProcess shape[1]: %d shape[2]: %d shape[3]: %d",
               shape[1],
               shape[2],
               shape[3]);
  hbSysFlushMem(&(tensor.sysMem[0]), HB_SYS_MEM_CACHE_INVALIDATE);
  float x = reinterpret_cast<float *>(tensor.sysMem[0].virAddr)[0];
  float y = reinterpret_cast<float *>(tensor.sysMem[0].virAddr)[1];
  if (!std::isfinite(x) || !std::isfinite(y) ||
      x < -1.0F || x > 1.0F) {
    RCLCPP_WARN(
      rclcpp::get_logger("LineFollowerPerceptionNode"),
      "Model returned invalid line coordinates: (%f, %f)", x, y);
    return -1;
  }
  result->x = (x +1.0) * 960.0;
  result->y = 500.0 + (y + 1.0) * 224.0;
  RCLCPP_DEBUG(rclcpp::get_logger("LineFollowerPerceptionNode"),
               "coor rawx: %f,  rawy:%f, x: %f    y:%f", x, y, result->x, result->y);
  return 0;
}

int main(int argc, char* argv[]) {

  rclcpp::init(argc, argv);

  auto node = std::make_shared<LineFollowerPerceptionNode>("GetLineCoordinate");
  if (!node->is_ready()) {
    rclcpp::shutdown();
    return 1;
  }
  rclcpp::spin(node);

  rclcpp::shutdown();

  RCLCPP_WARN(rclcpp::get_logger("LineFollowerPerceptionNode"), "Pkg exit.");
  return 0;
}
