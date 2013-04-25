#/*******************************************************************************
# * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# *       http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
# *******************************************************************************/

#####
# Ruby script for running ruote workflows.
# Workflow is injected to the script using the $workflow variable.
#
# Additionally, a ruote participant for running java code is included.
#
# author: Idan Moyal
# since: 0.1
#

require 'rubygems'
require 'ruote'
require 'net/http'
require 'java'
require 'participants'

def to_map(java_map)
  map = Hash.new
  java_map.each { |key, value| map[key] = value }
  map
end

def create_dashboard
  dashboard = Ruote::Dashboard.new(Ruote::Worker.new(Ruote::HashStorage.new))
  dashboard.register_participant 'java', JavaClassParticipant
  dashboard.register_participant 'rest_get', RestGetParticipant
  dashboard.register_participant 'rest_put', RestPutParticipant
  dashboard.register_participant 'state', StateCacheParticipant
  dashboard
end

def parse_workflow(workflow)
  Ruote::RadialReader.read(workflow)
end

def execute_ruote_workflow(dashboard, workflow, workitem_fields, wait_for_workflow = true)
  wfid = dashboard.launch(workflow, to_map(workitem_fields))
  if wait_for_workflow
    dashboard.wait_for(wfid)
  else
    wfid
  end
end

def wait_for_workflow(dashboard, wfid)
  dashboard.wait_for(wfid)
end