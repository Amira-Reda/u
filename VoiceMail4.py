import requests
import json
import time
from time import gmtime
import pytz
import datetime
from datetime import timedelta
import threading
from rest_framework.response import Response
from rbasis.views import *
from AutoserviceDashboardApi.database.models import *
from AutoserviceDashboardApi.database.serializers import *
from AutoserviceDashboardApi.module.glb.constant.http_ret_code import *
from AutoserviceDashboardApi.module.glb import twilio as glb_twilio
from AutoserviceDashboardApi.module.glb import email as glb_email
from AutoserviceDashboardApi.module.atsd.constant.project import *
from AutoserviceDashboardApi.module.atsd import basic as atsd_basic
from AutoserviceDashboardApi.module.atsd import voicemail as atsd_voicemail

#***********************************************************************************
# ------------------------ @Class: VoiceMail Api ------------------------
#-----------------------------------------------------------------------------------
class VoiceMail(ShAPIView):
    queryset = tbl_voicemail.objects.all()
    serializer_class = tbl_voicemail_serializer

    # ***********************************************************************************
    # @Function: [GET]
    # @Return: Method Not Allowed
    # -----------------------------------------------------------------------------------
    def list(self, request, *args, **kwargs):
        return Response([], status=HttpResponse405)

    # ***********************************************************************************
    # @Function: [GET]
    # @Return: Method Not Allowed
    # -----------------------------------------------------------------------------------
    def retrieve(self, request, *args, **kwargs):
        return Response([], status=HttpResponse405)

    # ***********************************************************************************
    # @Function: [POST]
    # @Return: Method Not Allowed
    # -----------------------------------------------------------------------------------
    def create(self, request, *args, **kwargs):
        try:
            key_ary = ["message", "caller_phone", "advisor_phone", "caller_name", "ok_text", "type", "delay_time"]
            if atsd_basic.checkKeysInDict(key_ary, request.data) == False:
                return Response({"error":"Missing parameters"}, status=HttpResponse500)
            if int(request.data["type"]) != 1 and int(request.data["type"]) != 2:
                return Response({"error":"Type error"}, status=HttpResponse500)

            if request.data["caller_phone"][0] != "+":
                return Response({"error": "Invalid caller phone number"}, status=HttpResponse500)

            advisor = atsd_basic.getAdvisorByPhoneNumber(request.data["advisor_phone"])
            if advisor == None:
                return Response({"error": "Invalid advisor phone number"}, status=HttpResponse500)

            cur_gmtime = time.gmtime()
            voicemail_obj = tbl_voicemail()
            voicemail_obj.message = request.data["message"]
            voicemail_obj.caller_phone = request.data["caller_phone"]
            voicemail_obj.advisor_phone = request.data["advisor_phone"]
            voicemail_obj.caller_name = request.data["caller_name"]
            voicemail_obj.ok_text = request.data["ok_text"]
            voicemail_obj.type = request.data["type"]
            voicemail_obj.delay_time = int(request.data["delay_time"])

            voicemail_obj.time = datetime.datetime(cur_gmtime.tm_year, cur_gmtime.tm_mon, cur_gmtime.tm_mday,
                                                   cur_gmtime.tm_hour, cur_gmtime.tm_min, cur_gmtime.tm_sec, tzinfo=pytz.UTC)
            voicemail_obj.save()
            #newly add 'US/Central' timezone
            UTC = pytz.utc
            timeZ_Ce = pytz.timezone('US/Central')
            fmt = '%Y-%m-%d %H:%M:%S'
            current_time = datetime.datetime.now(timeZ_Ce).strftime(fmt)
            voicemail_obj.time = current_time
            voicemail_obj.save()

            # ---------- if voicemail case ---------- #
            if int(request.data["type"]) == 2:
                voicemail_obj_list = list(tbl_voicemail.objects.filter(type=1, status__lte=1).order_by("-time"))
                if len(voicemail_obj_list) > 0:
                    voicemail_obj = voicemail_obj_list[0]
                    voicemail_obj.delete()


            return Response({}, status=HttpResponse200)

        except Exception as e:
            return Response({"error":"Unknown error -> " + str(e)}, status=HttpResponse500)

    # ***********************************************************************************
    # @Function: [UPDATE]
    # @Return: Method Not Allowed
    # -----------------------------------------------------------------------------------
    def update(self, request, *args, **kwargs):
        return Response([], status=HttpResponse405)

    # ***********************************************************************************
    # @Function: [DELETE]
    # @Return: Method Not Allowed
    # -----------------------------------------------------------------------------------
    def destroy(self, request, *args, **kwargs):
        return Response([], status=HttpResponse405)
