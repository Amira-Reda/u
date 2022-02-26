import json
import time
import pytz
import datetime
from time import gmtime
from datetime import timedelta
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
# ------------------------ @Class: SmsCallback Api ------------------------
#-----------------------------------------------------------------------------------
class SmsCallback(ShAPIView):
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
            from_number = request.data["From"]
            to_number = request.data["To"]
            message = request.data["Body"]

            company_obj = tbl_company.objects.get(twilio_phone_number=to_number)
            advisor_obj_list = list(tbl_advisor.objects.filter(company_id=company_obj.id))
            advisor_phone_list = []
            for advisor_obj in advisor_obj_list:
                advisor_phone_list.append(advisor_obj.phone_number)

            # ---------- get correct voicemail ---------- #
            voicemail_obj_list = list(tbl_voicemail.objects.filter(status__lt=3).order_by("-time"))
            voicemail_id = -1
            for voicemail in voicemail_obj_list:
                if voicemail.caller_phone == from_number and voicemail.advisor_phone in advisor_phone_list:
                    voicemail_id = voicemail.id
                    break

            if voicemail_id == -1:
                raise Exception()
            voicemail_obj = tbl_voicemail.objects.get(id=voicemail_id)
            advisor_obj = tbl_advisor.objects.get(phone_number=voicemail_obj.advisor_phone)


            # ---------- update voicemail status & save message ---------- #
            voicemail_obj.caller_replied = 1
            voicemail_obj.time = datetime.datetime.now()
            voicemail_obj.save()

            vm_reply_response_obj = tbl_voicemail_response()
            vm_reply_response_obj.vm_id = voicemail_id
            vm_reply_response_obj.replier_name = "Caller"
            vm_reply_response_obj.message = message

            cur_gmtime = time.gmtime()
            vm_reply_response_obj.time = datetime.datetime(cur_gmtime.tm_year, cur_gmtime.tm_mon, cur_gmtime.tm_mday,
                                                           cur_gmtime.tm_hour, cur_gmtime.tm_min, cur_gmtime.tm_sec, tzinfo=pytz.UTC)
            vm_reply_response_obj.save()

            response_tpl_map = {
                "advisorName": advisor_obj.name,
                "callerName": voicemail_obj.caller_name,
                "callerNumber": voicemail_obj.caller_phone,
                "callerMessage": message,
                "okToText": voicemail_obj.ok_text
            }
            response_tpl = atsd_voicemail.updateResponseTemplate(advisor_obj.caller_text_response_template, response_tpl_map)

            # ---------- send sms, email to advisor ---------- #
            sms_allow_from_hour, sms_allow_from_min = atsd_basic.spliteTime(advisor_obj.sms_allowed_from)
            sms_allow_to_hour, sms_allow_to_min = atsd_basic.spliteTime(advisor_obj.sms_allowed_to)
            email_allow_from_hour, email_allow_from_min = atsd_basic.spliteTime(advisor_obj.email_allowed_from)
            email_allow_to_hour, email_allow_to_min = atsd_basic.spliteTime(advisor_obj.email_allowed_to)

            cur_gmtime = gmtime()
            cur_time = datetime.datetime(cur_gmtime.tm_year, cur_gmtime.tm_mon, cur_gmtime.tm_mday,
                                         cur_gmtime.tm_hour, cur_gmtime.tm_min, cur_gmtime.tm_sec, tzinfo=pytz.UTC)
            cur_time = cur_time + timedelta(hours=-7)
            cur_hour = cur_time.hour
            cur_min = cur_time.minute

            sms_flag = True
            if cur_hour < sms_allow_from_hour or (cur_hour == sms_allow_from_hour and cur_min < sms_allow_from_min):
                sms_flag = False
            if cur_hour > sms_allow_to_hour or (cur_hour == sms_allow_to_hour and cur_min > sms_allow_to_min):
                sms_flag = False

            email_flag = True
            if cur_hour < email_allow_from_hour or (
                    cur_hour == email_allow_from_hour and cur_min < email_allow_from_min):
                email_flag = False
            if cur_hour > email_allow_to_hour or (cur_hour == email_allow_to_hour and cur_min > email_allow_to_min):
                email_flag = False

            r_tpl = response_tpl.replace("{{responseLink}}",
                                         "http://dash.autoservice.ai/user/voicemail/response/" + str(voicemail_obj.id) + "/0")

            if sms_flag == True:
                glb_twilio.sendSms(company_obj.twilio_account_sid,
                                   company_obj.twilio_auth_token,
                                   company_obj.twilio_phone_number,
                                   voicemail_obj.advisor_phone,
                                   r_tpl)

            if email_flag == True:
                glb_email.sendEmail(from_str="Autoservice.ai",
                                    src_email=GMAIL_ACCOUNT["email"],
                                    src_pwd=GMAIL_ACCOUNT["password"],
                                    dest_email=advisor_obj.email,
                                    subject="Autoservice.ai Notification",
                                    content=r_tpl,
                                    smtp_server_domain="smtp.gmail.com",
                                    smtp_server_port=587)

            # ---------- send sms to buddies ---------- #
            buddy_list = json.loads(advisor_obj.buddy_list)
            idx = 1
            for buddy in buddy_list:
                r_tpl = response_tpl.replace("{{responseLink}}",
                                             "http://dash.autoservice.ai/user/voicemail/response/" + str(voicemail_obj.id) + "/" + str(idx))
                if sms_flag == True:
                    glb_twilio.sendSms(company_obj.twilio_account_sid,
                                       company_obj.twilio_auth_token,
                                       company_obj.twilio_phone_number,
                                       buddy["phone_number"],
                                       r_tpl)

                if email_flag == True:
                    glb_email.sendEmail(from_str="Autoservice.ai",
                                        src_email=GMAIL_ACCOUNT["email"],
                                        src_pwd=GMAIL_ACCOUNT["password"],
                                        dest_email=buddy["email"],
                                        subject="Autoservice.ai Notification",
                                        content=r_tpl,
                                        smtp_server_domain="smtp.gmail.com",
                                        smtp_server_port=587)
                idx += 1

            return Response({}, status=HttpResponse200)

        except Exception as e:
            return Response({}, status=HttpResponse500)

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